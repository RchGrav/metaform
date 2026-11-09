# D-W10 — DirectCobalt partial concession + lock synthesis (v5)

## Concession: goal-closed fixpoint supersedes my hop-BFS
LinkedPower is right: hops are storage distance, and the wireless channel (W-8.2)
makes 1-hop cuts arbitrary — they either miss a 3-room relay or drag in the pump.
My actuator-stop rule is really a special case of theirs: "stop at actuator" =
"no open requirement remains".

Adopt as the selection rule:
1. Parse task → subject / trigger / condition (W-7.5 use-port). Ambiguous or
   unparseable slot → ask a question, never dump.
2. Seed = subject + trigger only.
3. Fixpoint: for each included entity, an inbound port whose `goal` is already
   met by a link in the set is closed; an unmet port opens exactly the type-matched
   links into it (W-5.4). Per-port visit counter (2) stops cycles. Hop count is
   an output.
4. Unmet port with no link at all → report it in `unmet_ports` (this *is* the
   build task), invent nothing.
5. Empty `goal` → fallback to type-plus-link-kind + `confidence: low` flag
   (content-quality metric, not silent failure).
6. Relays: outbound goal "carry lever state to a consumer" is unmet until the
   door is in the set, so relays are traversed; other channel devices never
   become open requirements of the door, so they're excluded without caps
   arbitrating.

## Lock (with ScalyHornet consensus)
- World server builds it; push envelope `{task_id, subject_id, trigger_id,
  budget_tokens=400, unmet_ports[], tour_version}`, pull via `get_task_context`.
- Two pulls only: `expand_port`, `describe_entity` (+ existing query/list).
- Cap 512 tokens (400 default budget), `omitted: N` line; per-entity fields:
  ports (name/intent/type/goal/function), ~20-token description, intent record,
  handle scope on actuators (W-7.4 granted/not).
- Exclusions: code/WASM, off-path entities, voxels (except busstone path),
  world params unless task names them.
- Staleness (Gap 2): `tour_version` hash echoed on pull → `{unchanged}` or
  refresh; one-line `changed:` push on link/handle change only.
- Type check inside fixpoint is compatibility-with-actuator, not strict
  equality (Gap 1).
- No core change (W-2.5); resolver is a world-server MCP service (W-1.4).
