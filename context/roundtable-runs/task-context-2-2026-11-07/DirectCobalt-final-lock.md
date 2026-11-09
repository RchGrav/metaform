# D-W10 final lock — DirectCobalt (v6)

Confirm ScalyHornet synthesis, with two DirectCobalt amendments:
1. **BluntDiode's declared/observed/requested distinction is required, not
   optional.** W-5.5 intent is *declared*, link state is *observed*, task text is
   *requested*. Conflicts task-vs-intent are explicit fields, never silently
   resolved. This prevents the agent mistaking a planned link for existing
   wiring — the exact failure mode of "inventing entities" LinkedPower's check
   (3) targets.
2. **Consumer-side expansion for changed ports.** LinkedPower's fixpoint walks
   inbound unmet goals only. BluntDiode is right that changing a port's meaning
   (lever output also feeding an alarm) requires including *other consumers'* of
   that port. Fixpoint must run both directions: inbound-goal closure AND
   consumer-of-changed-port contracts. The alarm passes check: lever far away
   (wireless) still included; unrelated neighbours don't grow the packet.

## Final locked D-W10
1. Bind task → persistent entity IDs; creation requirements marked `create:`,
   never fabricated IDs. Ambiguous binding → question/candidate list (≈6
   tokens), never a dump.
2. Selection = port-goal fixpoint over three edge kinds: port-links (W-5.4),
   joints (W-4.4), grant handles (W-7.4); per-port visit counter; empty goal →
   type+link-kind fallback with `confidence: low`. Hop count is an output.
3. Seed = all task-named entities (slots are a common-case shaper, not a hard
   schema — multi-input machines don't reduce to subject/trigger).
4. Packet distinguishes declared / observed / requested; conflicts explicit.
5. Consumers of changed ports included (boundary contract only); stop at
   unchanged objects' interfaces unless evidence is uncertain.
6. Budget: never silently truncate required contracts → `needs_narrowing` with
   frontier + next bounded expansion. Optional detail may be omitted (`omitted: N`).
7. World-server-built; push envelope + pull (`get_task_context`, `expand_port`,
   `describe_entity`); staleness via tour_version + `changed:` one-liners;
   handle scope per actuator; server-side inclusion trace (free to agent).
8. Spatial/physics facts (hinge limits, swept volume) only on specific need.
