# DirectCobalt — D-W10 Task Context: selection + delivery

## Principle
Task names a behaviour; system derives closed relevant set, never scans world. Pull via ACP (W-11.7) with push of envelope only. Budget: example below ~180 tokens.

## Selection algorithm (over W-5 graph in LadybugDB) — v2 synthesis with ScalyHornet
1. Seed: entities/ports explicitly named in task, or at task anchor (player position/selected entity). If none named, seed = nearest `use`-port entity within radius. Agree with ScalyHornet: no seed → no tour, agent asks (no nearby-dump fallback).
2. Expand by bounded BFS along links only (W-5.4) + link kind (W-8.2), max 8 entities, max 512 tokens. **Stop rule (adopted from ScalyHornet):** expand from each seed outbound until reaching an actuator port (inbound intent + goal describing an action on a world object per W-7.2–7.4), rather than a fixed hop count. Hop 1 unconditional; hop 2 only if (a) **type-compatibility, not equality** (per ScalyHornet Gap 1): an intermediate is allowed if its outbound WIT type is compatible with the task's named actuator/signal (adapters bool→f32, motor-driving relays pass; unrelated power-grid types fail) AND (b) the intermediate's goal/function or description matches a task term. Mid-path non-actuator relays render minimally (id + one-line description) so chains never inflate budget. Lever→relay→door included; lever→power-grid excluded. No TF-IDF server-side — structural stop is deterministic; agent may pull deeper if needed. Actuator blocks include handle scope (W-7.4): granted/not-granted. Fallback: if no actuator found within 2 hops, stop and emit `omitted: actuator not reached`.
3. Include per entity: manifest (W-5.3) ports' name/intent/type/goal/function, `description` (truncated ~20 tokens), `intent` record (W-5.5), current link state. Exclude: voxels (except link path if busstone), code (WASM), unrelated entities, global physics/params unless task touches them.
4. Prune: drop ports with no link and not named in task; dedupe by entity id; if over cap, drop lowest-relevance (farthest, non-seed) and append one line `omitted: N entities`.
5. Deterministic order: seed first, then BFS distance, then alphabetical by entity id.

## Delivery format (ACP pull, with push envelope)
Envelope pushed at task start: `{task, budget=512, tour_id}`. Agent calls `get_task_context(tour_id)` → returns:
```
Task: door opens when lever pulled
Entities:
  lever#12 [use:inbound bool=on; out:bool]
    desc: player pulls handle
    intent: toggles on pull
  relay#30 [in:bool; out:bool]  (hop2, task-matched)
    desc: passes signal when powered
  door#47 [in:bool; joint:motor]
    desc: hinged slab, opens 90deg
    intent: open when in=true
Links:
  lever#12.out:bool -> relay#30.in:bool (wireless ch=1)
  relay#30.out:bool -> door#47.in:bool (wireless ch=1)
Handles: lever#12, relay#30, door#47 (W-7.4)
omitted: 0 entities
```
On-demand only: `query_entity`, `list_links`, `renderSubgraph(id, depth)` for excluded detail. No stats/inventory/docs dump (contrast Mindcraft 11.1).

## Staleness + lifecycle (adopted from ScalyHornet Gap 2)
Envelope carries `tour_version` (hash of tour entity ids + link/handle state). Pull echoes it: server returns `{unchanged}` or a refreshed tour under the same `tour_id`. Additionally, server pushes a one-line `changed: <entity>.link|handle` only when a tour entity's link or handle actually changes — zero cost in the common case. Tour expires on task close; refresh reuses the id.

## Why it fits spec
Uses only W-5.3/5.4/5.5 fields, respects W-11.6 brevity, W-2.5 no core change (resolver is world-server service), W-7.4 handles bound to context set.
