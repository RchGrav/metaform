# StonyPrism: Task Context Selection & Delivery (D-W10 / W-5.6)

## Principle
Task context = closed graph slice, not retrieval. Selection is deterministic from task anchors; delivery is one minimal manifest envelope, expandable only on demand via ACP pull (W-11.7).

## Selection algorithm
1. **Anchors**: task specifies entity ids (or `new:<kind>` for to-be-created) + optional region/box + verb templates (e.g. door-opens-on-lever). Anchors are the ONLY seeds.
2. **1-hop expansion**: include anchors' ports, links (W-5.4), and directly linked entities' ports. No transitive closure beyond 1 link hop unless a port type forces it (e.g. lever→door via intermediate controller).
3. **Intent & manifest**: for each included entity, include W-5.3 manifest (name/intent/type/goal/function per port) + description + W-5.5 intent record, truncated: description ≤ 2 sentences, intent ≤ 3 lines. Omit voxel data, transforms beyond anchor-relative offsets.
4. **Relevance filter**: drop entities with no port path to any anchor; drop ports whose type cannot connect (type-mismatch prune). Cap: ≤ 8 entities, ≤ 32 ports, ≤ 4 links. If cap exceeded, rank by graph distance to anchor and cut.
5. **Negative context**: list explicitly EXCLUDED nearby entities by id+kind (prevents agent hallucinating them into build).

Example door/lever: anchors = {doorInstance, leverInstance}. Slice = both manifests + link lever.out→door.in + type + goals. No other world entities, no chunk data.

## Delivery format
Single JSON object (or WIT record), fields:
```
task, anchors[{id,kind}], entities[{id,kind,ports[{name,intent,type,goal,function}],links[],description,intent}], excluded[], budget{entities,ports}
```
Push once at task start (W-11.7 push). Pull-on-demand: agent may request `expand(entityId)` or `query(type/role)` via ACP, each pulls ≤ 1 additional entity with a budget check. No streaming world state.

## Why this wins
- Brief/targeted (W-11.6): slice size bounded by anchors, not world size.
- Deterministic & auditable: same anchors → same slice.
- Matches manifest model (W-5.2/5.3): reuses existing graph fields, no new ontology.
- Versus Mindcraft/Voyager retrieval: those retrieve skills/docs by similarity; here relevance is structural (port-connectedness), so no embedding index needed.

## Risks / open
- Intent records may be verbose → enforce truncation at write time (W-5.5).
- 1-hop may miss multi-stage wiring → allow agent-initiated expand, logged.
- New entities (`new:`) have no manifest yet → include template manifest from asset/code module being built.
