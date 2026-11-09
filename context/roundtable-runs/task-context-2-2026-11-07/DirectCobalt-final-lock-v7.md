# D-W10 final lock v7 — DirectCobalt

## Correction accepted: task-term matching was circular
LinkedPower is right and I was wrong. My hop-2 gate ("intermediate's goal matches
a task term") rejects an honestly-described generic relay ("pass signal when
powered") in the canonical task. My fallback `omitted: actuator not reached`
would silently drop the door. Both are withdrawn.

## Final selection rule (structural, no vocabulary, no type re-testing)
- **No type tests in the resolver.** W-5.4 type-checked every link at creation
  and refuses bad ones; legality = path existence. This also resolves
  ScalyHornet's consensus.md:26 contradiction (equal vs compatibility) — neither
  is needed.
- **Termination is structural (sink/through/consumer), from `function` +
  `intent` (W-5.3), never `goal` prose:**
  - Sink: inbound port + entity holds handle (W-7.4) or has unlinked outbound
    → tour ends (door).
  - Through: inbound+outbound or equal `function` fragments → admit, render
    one line (relay, adapter path).
  - Consumer-only (inbound, no outbound) → never entered (pump/lamp).
- Missing `function` → through + `low_confidence` flag; widens one line,
  never drops the sink.
- Any link path between two named seeds admitted in full (adapter case).
- Bidirectional (ScalyHornet): producers for unmet inbound goals; consumers
  only for ports whose existing behavior the task *modifies* (add ≠ repurpose),
  bounded by modified ports — additive tasks don't inflate.
- Seed = all task-named entities; ambiguity → question, never dump (modify class only, see below).
- Joints (W-4.4) + handles (W-7.4) are selection edges.
- Declared / observed / requested kept distinct; conflicts explicit.

## Two-class extension (adopted from LinkedPower creation-class)
The brief's example ("build a door...") names no existing entity, so seeding
yields ∅ and "which door?" is unanswerable. Classify before seeding:
- `create`: every named role resolves to zero entities → run the same fixpoint
  over *roles* (requirements from intent W-5.5); requirement closes when a
  host capability (W-7.2/W-4.4/W-7.5) can realise it; packet = roles +
  capabilities + top-3 by port signature from W-9.4 assemblies (never invented
  IDs; explicit "no assembly matches" is the legible failure).
- `modify`: ≥1 resolves → merged fixpoint above.
- Acceptance test: brief's text must return `class: create` with roles +
  templates + `requested_links` and no "which door?"; "the door won't open..."
  must return the modify fixpoint. Repair check: permit-enabled=false must
  expose the controller's `enabled` side dependency (unresolved frontier),
  never report behaviorally satisfied; adapter bool→f32 admitted by
  per-link equality while a direct bool→f32 link remains rejected by W-5.4.
## Connection ≠ satisfied behavior (adopted from BluntDiode)
- Keep `connection_state` and `behavior_evidence` separate. A wire is
  connectivity, never proof of satisfied behavior (controller needs
  trigger AND enabled; permit=false fails the task despite all links).
- At an intermediate controller, include the input/constraint contracts of
  its relevant output, not only the task-term-matching input. Without
  dependency metadata, expose other inputs as a bounded unresolved frontier
  rather than silently excluding them.
- Adapters: W-5.4 exact type equality per link; conversion is internal to
  the adapter (bool in, f32 out). No resolver-side compatibility test.
- Type equality issue resolved as LinkedPower said: legality = W-5.4 edge
  existence; equality holds per link by construction.
- Freshness: version every record read (incl. intent/manifest/constraints),
  watch empty ports, reselect on next pull; push alone is not freshness.

## Create-class build brief (adopted from ScalyHornet delta)
- Add `requested_links[]` from task causal structure, under *requested*
  (never observed): `lever.out:bool -> door.in:bool`. This is what the agent
  builds; without it create yields two disconnected templates.
- Rendering collapse: in create, observed layer omitted — empty by
  construction, a brevity feature. Modify keeps all three layers.
- `unmet_ports[]` in create also covers a requested link no template pair
  satisfies.

## Delivery (unchanged lock)
World-server-built; push envelope `{task_id, subject_id, trigger_id,
budget_tokens=400, unmet_ports[], tour_version, graph_seq}`; pull
`get_task_context` / `expand_port` / `describe_entity`; `needs_narrowing` over
silent truncation (required contracts never cut); `omitted: N` for optional
detail only; handle scope per actuator; server-side inclusion trace;
`graph_seq` distinguishes own-write from others'-write (re-plan vs resume).
