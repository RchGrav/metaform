# D-W10 FINAL LOCK v9 — DirectCobalt (post check-coverage audit)

## The lock
One resolver, two phases (create→modify flip on graph_seq bump, same tour_id),
over the merged selection rules. Everything in canonical v2 / my v8 stands,
plus the following corrections from the R1-32..34 round:

### Check-suite repairs (LinkedPower coverage table) — required before lock
- Check 5 split into **5a–5g** (all positive): task_class==create; roles ==
  [door, lever] with goal-bearing ports; requested_links contains
  lever.out:bool→door.in:bool; capabilities ⊇ {ports, actuators, handles};
  ≤3 templates with signatures; ids_invented==[]; no ambiguity question.
  Negative-only "no 'which door?'" is vacuous (empty packet passes it).
- Check 6 split into **6a–6e**: door#47 must be *present* (entity_ids),
  in blocked, reason_code `handle_not_in_user_grants`, no drivable claim,
  and an explicit `request:grant door#47.motor`. Dropping the door is failure.
- The packet **never says "satisfied"**: only `connection: link-present|none`
  + `behavior_evidence {declared, observed, unresolved}`. Check 7 becomes:
  2 frontier ports + permit contract + no satisfied-token. Checks 1–2 need
  `classify:` per entity line (relay=through, lamp absent=consumer-only).
- Fixture must include a refused direct bool→f32 link (check 3), and the
  packet prints the `modified(P)` diff (checks 4a/4b/8, else 4a≡8).

### Classifier correction (LinkedPower §6, over FangedMercy verb list)
Create test is purely index-based, no build-verb list:
`create iff every named role resolves to 0 matches`. "Build a door" when one
exists → modify (ambiguity rules handle the wording). Verb phrases the
follow-up question only. Mixed task: primary subject per ScalyHornet's
resolution; secondaries become `create:` elements in `unmet_ports[]`.

### requested_links from ports, not prose
Generate from role signatures: for each ordered role pair and port pair with
equal WIT type (W-5.4), emit `a.out:T -> b.in:T (requested)`. Two candidates
→ emit both + `needs_narrowing: which interlock?` (C3 applied to wiring).

### BluntDiode final amendments — adopted where they don't reopen the lock
- `graph_seq` orders, not authorship: correlate changes with mutation
  operation ids; version all records read incl. intent/manifest/constraints
  and empty adjacency; version-check on commit of a dependent edit.
- Role binding is per-role (`existing`/`create`/`unresolved`), not a single
  class boolean — mixed build+reuse reads as bound roles, not a class.
- Contract boundaries: sink/through/consumer is structural *admission*, not
  behavioral proof; behavioral claims stay in `behavior_evidence` (which the
  "never says satisfied" rule already enforces). Unknown dependencies expand
  as explicit frontier, never silently excluded.

### Lock condition
All 14 checks (1–14 incl. 5a–5g, 6a–6e) + the create→modify flip test
(same tour_id, class recomputed on graph_seq bump) must pass. A locked design
whose checks cannot fail is not tested — ship only the decidable forms.
