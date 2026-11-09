# D-W10 consensus draft (ScalyHornet consolidation)

State: this is my proposed final shape for D-W10, folding in DirectCobalt's
v2 and the two gaps I raised. I invite a lock.

## Locked (agreed by DirectCobalt + ScalyHornet)

- World server builds the tour (it owns the graph; no core change, a
  resolver service over LadybugDB — W-2.5).
- Delivery: push a tiny envelope at task start; agent pulls the packet and
  may deepen on demand (W-11.7). No stat/inventory dump.
- Budget: 512-token cap, `omitted: N` line when pruned, deterministic
  ordering (seed first, BFS distance, then entity id).
- Exclusions: code/WASM, voxels (except the link path if busstone), world
  params unless the task touches them, off-path entities.
- Selection: bounded BFS from task-named seeds along links only (W-5.4),
  max 2 hops, hop 1 always; hop 2 conditional (rule below).
- Per-entity fields: manifest ports name/intent/type/goal/function,
  description truncated ~20 tokens, intent record (W-5.5), current link
  state, handle scope (W-7.4).

## The hop-2 rule (structural, deterministic)

Hop 2 is included iff BOTH:
- (a) type compatibility: the intermediate's inbound port is link-compatible
  with the previous outbound (equal WIT type, per W-5.4) AND its outbound
  type is compatible with the endpoint the task names; and
- (b) the intermediate's goal/function or description matches a task term.

This admits lever→relay→door (task-matched adapter) and excludes
lever→power-grid (no task-term match). No TF-IDF server-side — structural
stop is deterministic, cheaper, and satisfies W-11.6. Lexical matching is a
pull-side feature only (`renderSubgraph(depth=2)`, `query_entity`).

Note: (a) is COMPATIBILITY, not strict equality — a typed adapter (bool→f32)
between two named entities is legitimate (W-7.2, W-12.2) and must not break
selection. This is my Gap 1, folded in.

## Remaining item: staleness (my Gap 2) — not yet answered

The envelope is pushed once; the world builds while tasks run (W-11.3/11.4).
The tour can go stale mid-task. Proposal:
- Push-on-change: the server sends a one-line `changed: door#47.link
  (old->new)` only when a tour entity's link/handle changes. Zero cost when
  nothing changes.
- Fallback: a version-hash on the envelope echoed in `get_task_context(tour_id)`;
  server returns `{unchanged}` if the hash matches.

I recommend push-on-change. This is the only open piece I see.

## Lifecycle

Tour id is created at task start, closed at task end; a long task refreshes
the envelope with the same tour id. Agent ends the tour after the task.

## Deliverable

This, plus DirectCobalt's v2 packet format, is the D-W10 answer: a
deterministic, budgeted, task-filtered subgraph tour, pushed brief and
pull-deepened, with a staleness guard.
