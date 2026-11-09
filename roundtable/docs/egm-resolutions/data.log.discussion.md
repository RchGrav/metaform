# Resolution: discussion record (`data.log.discussion`)

Prepared by ExactTiger. This resolves the findings; it does not implement the proposed code changes.

## Basis and intended contract

The supplied source consists of `record.rs` and `events.rs`. References below are relative to `source/`. Claims about `turn.rs`, `engine.rs`, `app.rs`, `tables.rs`, ACP shutdown, and the historical audit cannot be independently checked here. Their absence limits verification; it does not make the reported problems false.

Keep the author's goal of a complete table audit, including participant prompts and replies. Correct the description of the current implementation: it is an append-only subscriber to the event bus, not an implemented event-sourced engine or a demonstrated source of prompt-builder state. Distinguish the desired contract from current coverage and failures. Fix loss and missing audit data in code rather than making silent loss the accepted contract.

The absence of prompt fields in `events.rs` alone does **not** prove prompts are absent from the record: the recorder consumes `bus::Envelope`, including events from other publishers, as its ACP/monitor routing explicitly anticipates. Conversely, a bus tap alone cannot prove that every prompt was received by an agent. Completeness requires evidence about all relevant publishers and the capture boundaries.

## Decisions by finding

### GF1 — Right about the responsibility mismatch; qualify the title

`record.rs:38–57` only opens and appends a file. It implements no history query or prompt-construction API. Change the wants/decision text to distinguish the prompt builder's need for accepted history and deferred notices from this component's duty to persist events for audit. Attribute the live context source to the engine/prompt builder after checking the cited, unavailable files. Do not add disk reads to the prompt path merely to make the old description true.

“Does not supply prompt content” concerns serving context to the builder; it does not establish that prompt text is never persisted. Check the ACP prompt event publishers separately before claiming existing prompt capture is absent or complete. Explain that distinction in the description.

### GF2 — Right: event sequence is not a canonical turn number

`record.rs:14` records an envelope `seq`; `FloorGiven` has `round`, and `Contribution` has an optional `id`. Pass, skip and failure events have no explicit turn identity (`events.rs:38–55`). Neither a bus event sequence, a round number, nor a contribution label is a canonical logical turn identifier. The particular `R{topic}-{n}` format and assignment of null IDs rely on the unavailable producer code.

Retain the decision's explicit requirement for canonical turn identity and change the producer/event schemas: allocate a table-wide, monotonic turn number once per scheduled seat opportunity, including opportunities that are skipped. Carry it on the floor/skip and associated outcome events, including accepted/rejected contributions, passes and failures. Preserve the same number through evaluation or background-work continuation of that opportunity; allocate a new number only for a new opportunity. Topic changes must not reset it. Keep contribution IDs and bus `seq` for their separate purposes. Define this behavior in the description so missing and repeated outcomes can be audited without guessing from event adjacency.

### GF3 — Right about source ownership and absent explicit counts

Remove “source for all three” from the current implementation description: this writer does not implement replay, distribution, or deferred-notice consumption. Record those operations as responsibilities of the live engine, with this component retaining the emitted evidence. Accepted text, `scores`, `reasons`, `limit` and `judged` do exist in `Contribution`; do not describe all outcome information as missing.

There are no explicit truncation counts in the supplied contribution or proposal schemas (`events.rs:39–59`). The reported rejection and 512-unit proposal behavior requires confirmation in `turn.rs`. Document over-limit rejection separately from text truncation: rejected text has not necessarily been shortened. For actual shortening, change the producing code to emit original length, retained length, measurement unit and limit, and preserve the original input or an explicitly linked capture if the complete-reply contract is to hold. Keep the delivered/retained text distinguishable from the original reply. A limit or a prose reason alone cannot establish how much was removed.

### GF4 — Right about the early boundary; routing needs qualification

`record.rs:51–53` exits immediately after attempting to append `roundtable.ended`. Consequently it cannot record any later shutdown events. The specific ordering of SessionClosed and HarnessExited is reported by the reviewer, not verified in this snapshot.

Change recorder lifecycle management to keep the subscription active through table-owned shutdown, then signal a terminal recording boundary after relevant publishers have finished, drain preceding events and await recorder completion. Merely deleting the break and waiting for a shared bus to close can leave a table recorder alive indefinitely. Document whether `roundtable.ended` means discussion ended or capture ended; they must not be conflated.

Filtering other tables and unrelated global events is correct. The problem is table-relevant events without routable identity, not that every event on a shared bus must be copied into every file. Require those publishers to supply a table identity or a supported harness identity. Identify genuinely unowned events as out of scope and surface unexpected attribution failures through diagnostics. Do not assign unknown events arbitrarily to a table.

### GF5 — Right; serialization failure is worse than the wording suggests

`record.rs:50` discards append errors. Initial directory/open errors are returned, but asynchronous failures are not; `spawn_recorder` returning `Ok(())` therefore does not establish recording success. Return an observable completion/error handle, propagate write failures to the table manager, and mark the audit incomplete when writing fails. Define and await the final persistence boundary; do not claim crash durability merely because an append succeeded.

`line()` substitutes JSON null on serialization failure (`record.rs:17`). **In the recorder, that line is then dropped:** `table_of(null)` returns `None`, so the filter at line 47 continues before `writeln!`. Thus the finding is correct about lost payloads, but its assertion that the recorder writes those failed events as `data:null` is inaccurate.

Change serialization handling to report an explicit error rather than silently substituting null. Preserve event name/sequence and independently available routing identity in failure diagnostics; record an attributable failure marker where possible. If table identity itself is unavailable, report the failure outside the per-table file and expose incomplete coverage rather than claiming a successful complete record. Serialization diagnostics cannot restore a payload that was never serialized.

### GF6 — Right; separate verified schema from reported integration

Expand the description with:

- One JSON object per line: `seq` is the bus envelope sequence, `at_ms` is the envelope timestamp in Unix milliseconds, `event` is its wire name, and `data` is its serialized payload. These are envelope fields, not a canonical turn schema. The timestamp currently defaults to zero if it predates the Unix epoch.
- Append mode, table filtering and lifecycle boundaries. Describe order as the order received by this tap; do not promise additional delivery or durability guarantees without inspecting the bus.
- Routing precedence: a string `data.table` wins; otherwise use the prefix before the first slash of a string `data.harness` or object `data.harness.id` (`record.rs:24–35`).
- Default file location, configuration override and actual readers, after checking their implementations.

The reviewer reports `<ROUNDTABLE_HOME|~/.roundtable>/tables/<id>/record.jsonl` and readers in `app.rs:279–341`. That is a concrete lead for the documentation update, but `spawn_recorder` accepts an arbitrary `path`, so this module does not establish that default or those readers. Avoid inventing reader behavior from line numbers alone.

### GF7 — Right: make the architectural roles explicit

Replace the inconsistent current-state claims with: “The discussion record persists table-attributable bus events for audit. The live engine maintains the state used to build participant deliveries; record replay is not implemented by this module. Complete prompt/reply capture is the intended coverage, subject to the documented producer and lifecycle gaps.” Verify live-state ownership against the cited engine code before treating that clause as independently confirmed.

Outcome events and prompt/reply events can coexist in one audit file; those are compatible scopes. The contradiction is assigning the file authority for live context without an implemented read/replay path, and describing desired completeness as already achieved. Do not introduce a second store or replay architecture solely to resolve the wording.

### GF8 — Right: define the local vocabulary

Add a short glossary or links to authoritative definitions:

- **Table:** one collaboration instance and the routing scope of a record file.
- **Seat:** a participant slot associated with a harness/session; distinguish the slot from the agent's display name.
- **Seat availability:** whether that slot can currently take a turn; identify which readiness, failure, departure and work events establish it rather than claiming a recorded boolean exists.
- **Topic:** the current subject within the continuing table objective; changing topic does not start a new table record.
- **Disposition:** the handling/outcome of a submission, including acceptance, evaluator rejection or limit rejection, and any deferred feedback.
- **Veto:** evaluator rejection of a contribution, with feedback held for its author's next delivery as described in the map.
- **JEV:** the evaluator responsible for contribution checks and recorded judging results; obtain its official expanded name and criteria from its own documentation rather than guessing the acronym.
- **Truncation:** removal of part of text, with the measured counts and unit distinguished from rejection for exceeding a limit.
- **Canonical turn number:** the table-wide opportunity identifier specified in GF2, explicitly marked as a required addition rather than an existing event field.

### GF9 — Right: rationale is not traceable

Replace the bare audit codes with a stable path/link to the audit and anchors for E05, E06 and D01–D05, plus a short statement of the relevant observed behavior. Define “turn-label drift” from that evidence (what identifier differed from what expected identifier). No audit is supplied here, so the historical claim cannot be verified. If the audit cannot be recovered, mark it as an unverified historical account and use the present source references for the current defect rationale; do not fabricate a link or a historical diagnosis.

### GF10 — Right; duplicate of the location portion of GF6

Resolve together with GF6. State that the application creates one file per table, give the configured/default directory once verified, and distinguish that application convention from `spawn_recorder`'s caller-supplied path. No independent recorder code change is needed for this documentation omission.

### GF11 — Right: make missing request capture explicit

Replace “request ... had to be rebuilt” with the precise missing artifact: according to the author's gap statement, an original JEV request was not captured and a later reconstruction was necessary. Link the reconstruction/incident if available and label reconstructed input as reconstructed, not as the exact original request.

Retain this as a current gap until verified fixed. To meet the complete audit goal, have the evaluator publisher emit the actual assembled request and corresponding response, correlated to table, seat, turn and evaluation attempt. Existing contribution scores/reasons are outcome summaries, not evidence of the full evaluator exchange. Document separately the verified lifecycle/write/serialization gaps (GF4–GF5) and any prompt publisher gaps found by inspection; do not assert that all other traffic is captured merely because only one historical omission was listed.

### GF12 — Right about missing map conventions; small documentation fix

Define or link `role`, `name_length`, and `Intent` in the functional map's shared schema. State the reference point for send/receive explicitly. In these wants entries, the apparent intended direction is that the prompt builder receives history and the manager sends outcomes; confirm that against the map convention. `name_length: 2` matches the two words in “discussion record,” but that observation is not an authoritative schema definition. The meaning of `SE` cannot be derived from these files. Do not invent its expansion or add map metadata to runtime events.

## Verification expected when the fixes are implemented

Check canonical turn correlation across rejection, pass, skip, failure, background work and topic changes; distinguish rejected over-limit text from actual shortening; exercise append and serialization failure reporting; and verify that shutdown events precede successful recorder completion without including another table's traffic. Inspect the missing publishers and readers before certifying prompt/evaluator capture or documenting application paths. This decision-only change requires no runtime test run.

---

## Addendum: net-new refinements from the roundtable discussion (GlowingMarten)

These complement, and do not replace, ExactTiger's decisions above. Verified against `record.rs` / `events.rs` in `source/`.

**GF5 — one clarification that strengthens ExactTiger's correction.** The finding claims unserializable payloads are "written as data:null." ExactTiger (line 45) correctly notes they are actually DROPPED: `line()` sets `data = null` (record.rs:17), then `table_of(&line["data"])` calls `data.get("table")` on a null value → `None` → `table_of` falls through to `harness_id` → also `None` → returns `None` → the filter at record.rs:47 `continue`s before `writeln!`. So the finding is right that payloads are LOST but wrong about the mechanism (not written as null, skipped). The fix must therefore emit an attributable failure marker OUTSIDE the routing filter, or the diagnostic itself will be dropped too. This is a real consequence: any fix that relies on the normal `line()` → `table_of` → `writeln!` path cannot record its own serialization failures.

**GF1 — the prompt-field argument cuts both ways.** ExactTiger (line 11) is right that `events.rs` having no prompt event does not PROVE prompts never reach the file, because `spawn_recorder` consumes a generic `bus::Envelope` from any publisher. But the reverse also holds: nothing in the shipped `record.rs`/`events.rs` demonstrates a prompt IS captured. So the honest description is "prompt/reply capture is the intended coverage, unverified" — which is exactly what ExactTiger proposes for GF7 (line 62). The `elephant.built` claim "including each prompt text" should be downgraded from asserted to intended until the ACP/harness publishers are inspected.

**GF2 — cheaper implementation path, consistent with ExactTiger's GF2.** ExactTiger asks for a table-wide monotonic turn allocated per scheduled seat opportunity. The shipped schema already provides `round: u64` on `FloorGiven` (events.rs:38) and `RoundClosed` (events.rs:56), and `index: u64` on `TopicChanged` (events.rs:59). So the code change should REUSE the existing round counter by propagating `round`/`turn` onto `Contribution`, `Passed`, `Skipped`, `TurnFailed`, rather than introducing a second competing counter. Note also the finding's "No canonical turn number exists" is loose: a round number DOES exist; the precise defect is that per-turn *outcome* events carry no turn/round identifier, so a stored outcome cannot be tied to its canonical turn from the recorded event alone. Finding still right in substance.

**GF4 — the boundary is a design choice, not only a bug.** The `break` at record.rs:51–53 is a deliberate "capture only the active table lifecycle" boundary. The resolution is a choice, and the description must be updated either way: (a) document that the record intentionally stops at `roundtable.ended` and drop "every event", or (b) extend through teardown. ExactTiger recommends (b) with proper lifecycle/drain handling (line 37) — agreed, but note the ambiguity itself, not merely the `break`, is the defect. Also GF10 is a strict subset of GF6 (both concern the undocumented path/location); resolve them together, not as independent fixes.

**GF8 — prefer cross-references over a duplicated glossary.** Most undefined terms are defined in sibling map elements: JEV in `code.gate.quality`, seat/roster in `code.roster.participant`, topic in `code.selector.topic`, veto/deferred feedback in README §4.6 (already in `references`). A glossary that re-defines them will drift. Link to those elements; give local one-line definitions only for record-specific terms (`canonical turn number`, `table`, `disposition`, `truncation`). This is cheaper and keeps one source of truth.

**GF11 — partly misframed on "contradiction."** ExactTiger marks GF11 flatly "Right." It is right about vagueness, but the charge that the note "contradicts the 'complete record' claim" is weak: the elephant layer has a dedicated `gaps` field whose entire purpose is to acknowledge known absences, so a note in `gaps` is the author ADMITTING incompleteness, not contradicting the design goal. Also the gap IS named ("JEV's requests are not recorded"), so "without saying what else is missing" overstates — it is named, just not specified. Verdict: RIGHT on vagueness, PARTLY MISFRAMED on contradiction. Net: 11 of 12 findings fully right; GF11 qualified. (The GF5 mechanism correction above likewise means GF5 is right in substance, wrong in one detail.)

**Priority of work** (from GlowingMarten's independent verdicts, consistent with ExactTiger's):
1. Description reconciliation — record is a write-only, append-only bus-tap audit trail, NOT the distribution/disposition/context source (GF1, GF3, GF7). Highest value, single edit to `decisions` + `wants` + `elephant.built`.
2. Code fixes that a functional `want` or the design goal genuinely require: canonical turn identity (GF2), lossless lifecycle/routing/write/serialization handling (GF4, GF5), JEV-request capture (GF11).
3. Documentation: Storage/Representation section (GF6, GF10), glossary/cross-refs (GF8), linked audit evidence (GF9), map-schema note (GF12).

Auditability note: findings citing `turn.rs`, `engine.rs`, `app.rs`, `tables.rs`, `harness.rs` cite files NOT in this element's `source/` folder (only `record.rs`, `events.rs` are present). Those line-level citations are not independently checkable here; every verdict above is grounded in the two shipped files and the description.
