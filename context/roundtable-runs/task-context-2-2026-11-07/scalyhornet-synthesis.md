# ScalyHornet — synthesis of LinkedPower + BluntDiode + DC/SH (D-W10)

Three proposals are on the table. I assess each, then merge the strongest
parts into one lockable design.

## Assessment

1. DirectCobalt/ScalyHornet: bounded BFS from named seeds, actuator/type/term
   stop, token caps, push+pull. Correct shape, but the hop-bound is the
   weakest part — LinkedPower is right that it is a storage distance, not a
   task distance, and the shared bus (W-8.1/8.2) makes it unreliable.
2. LinkedPower: port-goal fixpoint — expand only *unmet* inbound-goal ports
   through type-matched links, repeat to a fixpoint. **Adopt as the
   selection rule.** It answers the relay case naturally and excludes the
   pump on the same channel by construction, and its `unmet_ports[]` report
   converges context with the build plan. Real improvement.
3. BluntDiode: dependency-following over *governed edges* (producers/
   consumers of changed ports), plus joints and granted handles as first-class
   selection edges; `needs_narrowing` instead of silent truncation; a
   server-side inclusion trace. **Adopt the two gaps below.**

## What I fold in from BluntDiode (missing from both LinkedPower and DC/SH)

- **Joints (W-4.4) and granted handles (W-7.4) are selection edges, not just
  port-links.** A door controlled by a motor through a joint may have no bus
  link to its mesh. LinkedPower's fixpoint only walks W-5.4 port-links, so it
  would miss the motor/joint. The fixpoint rule must treat three edge kinds:
  port-links (W-5.4), joints (W-4.4), and grant handles (W-7.4), each with
  its own goal-satisfaction test.
- **`needs_narrowing` contract.** LinkedPower and DC/SH cap tokens and just
  emit `omitted: N`. BluntDiode's stronger contract: never silently truncate
  a *required* contract; if required facts cannot fit the budget, return
  `needs_narrowing` with the frontier and the next bounded expansion. Keep
  `omitted: N` only for non-required detail.
- **Inclusion trace (server-side, not charged to the agent).** Each included
  fact records its source and a reason (`task-root`, `consumer-of-changed-port`,
  `joint-used-by-actuator`). This makes selection inspectable without spending
  the agent's context budget.

## What I keep from DC/SH

- Push-envelope + pull-deepening (W-11.7), world-server-built tour, budget,
  handle-scope safety (plan never uses an unreachable handle, W-7.4),
  staleness guard (push-on-change one-liner).

## One correction to LinkedPower

The subject/trigger/condition parse is a useful default but not a hard
requirement. Multi-input machines ("counter increments on button, resets at
10") do not reduce to two named actors cleanly. The fixpoint does not need
the slots — it needs the seed set (the named entities) and the behavioral
clauses. Keep the slots as the common-case shaper, but let the seed set be
"all entities named in the task," not only subject+trigger. Ambiguity still
returns a question, never a dump.

## The merged design (D-W10 final)

**Selection (LinkedPower fixpoint, extended):**
- Seed = entities named in the task (resolve; ambiguous → ask).
- Repeat to fixpoint: for each included entity, for each inbound port whose
  goal is not yet satisfied by an included link, follow the type-matched
  links (W-5.4) into it; also follow joints (W-4.4) and grant handles
  (W-7.4) that the task's behavior uses. Per-port visit counter stops cycles.
- Unmet inbound goals with no link → record in `unmet_ports[]` (the build
  plan).
- Hop count is an output, not an input.

**Rendering (task-filtered, budgeted):**
- Per entity: manifest ports (name/intent/type/goal/function), description
  truncated ~20 tokens, intent record, current link/joint/handle state.
- Exclusions: code/WASM, voxels except link path if busstone, world params
  unless the task touches them, off-path entities with satisfied goals.
- If required facts cannot fit the budget → `needs_narrowing` + frontier,
  not silent truncation. Non-required omissions → `omitted: N`.

**Delivery:**
- Push envelope at task start; pull `get_task_context(tour_id)`; deepen via
  `expand_port`/`describe_entity` (LinkedPower) and `renderSubgraph` (DC).
- Staleness: push-on-change one-liner (or version-hash fallback).
- Handle scope shown per actuator (W-7.4) so the agent never plans an
  unreachable grant.

**Inspectability:** server-side inclusion trace with per-fact reason.

## What I'd like the group to lock

1. Selection rule = port-goal fixpoint (LinkedPower), extended to
   joints+handles as edges (BluntDiode). Hop-bound retired.
2. `needs_narrowing` over silent truncation (BluntDiode).
3. Delivery frame as above (push+pull, budget, handle-scope, staleness).
4. Ambiguity → question, never dump (all).
