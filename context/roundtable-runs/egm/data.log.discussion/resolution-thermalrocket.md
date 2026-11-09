# Resolution — `data.log.discussion` (discussion record)

Reviewed by ThermalRocket. Evidence available in this folder: `source/crates/roundtable/src/record.rs` (71 lines) and `source/crates/roundtable/src/events.rs` (78 lines). Findings cite `turn.rs`, `engine.rs`, `app.rs`, `tables.rs`, `harness.rs`; those files are **not** in `source/`, so for claims about them I state whether my two available files corroborate, contradict, or are silent. Where silent, I accept the reviewer's premise but flag it as unverified so the disposition is auditable.

Term definitions used below (they are also the fix demanded by GF8):
- **JEV** — the judge/evaluator that scores a contribution and returns scores plus reasons.
- **disposition** — what the engine did with a turn: accepted, rejected, pass, skipped, failed, vetoed.
- **canonical turn number** — a single monotonic counter over the whole table, independent of topic, so any two events can be ordered.
- **seat** — one agent's seat at the table.

Overall verdict: **GF1, GF2, GF3 are correct and are the real problem** — the description's `decisions` entry claims the record is the *source* for distribution, dispositions and canonical turn numbers, and the code is not. **GF4–GF7 are correct as description/code mismatches.** **GF8–GF12 are correct as documentation gaps.** None of the twelve should be dismissed; the fix is mostly to the *description*, with a small code change for GF5 and a decision about scope for GF4.

---

## GF1 — Blocker: record does not supply prompt content
**Right.** `spawn_recorder` (record.rs:38–57) is a pure bus tap: it writes what it receives and hands nothing back. There is no read path in record.rs at all; the only functions are `line`, `table_of`, `harness_id`, `spawn_recorder`, and one test. The module doc (record.rs:1–2) says the log "holds … including every prompt each agent actually received", but the physical file only holds it *if* some publisher puts prompt text on the bus as an event. `events.rs` has no prompt event; the closest is `ChairSpoke`/`Notice`, and `Contribution` carries the *reply*, not the prompt sent to an agent. So the stated intent in the `elephant.built` account ("including each prompt text") is not backed by the event schema that I can see.

**Change:** in the description, split the two jobs the record is being asked to do. The record is an **audit sink**, not a **context source**. Delete the claim in `decisions` that the record is the source the prompt builder reads. Rewrite `code.builder.prompt`'s want to name the actual feeder (per the finding, in-memory `Table.log` + `Seat.notices` in turn.rs/engine.rs), and add a `gaps` line: "prompt text is not a first-class event, so record.jsonl contains it only insofar as the adapter emits it." If the owner wants prompts in the file (which `elephant.built` promises), the code change is to add a `PromptSent` event to events.rs carrying `{table, seat, text}` and publish it wherever the prompt is assembled — that is the only way the module doc at record.rs:1–2 becomes true.

## GF2 — Blocker: no canonical turn number
**Right.** events.rs confirms all three parts: `Contribution.id` is `Option<String>` (line 41), `Passed` has only `seat` (line 51), `Skipped` has `seat, reason` (line 54), `TurnFailed` has `seat, error` (line 55). Nothing in events.rs carries a `turn` field on any per-turn event; `FloorGiven` has `round` (table-wide round), not a turn index. So the decision's phrase "with its canonical turn number" describes a field the schema does not have. The reviewer's claim that accepted ids are `R{topic}-{n}` is a turn.rs fact I cannot check, but the `Option<String>` shape corroborates that ids are strings whose format the record does not police, and that rejected turns have no id.

**Change (description first, code if the claim is to be kept):** either
(a) drop "canonical turn number" from `decisions` and say the record is ordered by `seq` (record.rs:14) — which *is* a genuine total order and is sufficient for audit; or
(b) if per-turn numbering is actually needed downstream, add `turn: u64` to `Contribution`, `Passed`, `Skipped`, `TurnFailed` in events.rs, incremented once per `FloorGiven`. (b) is the stronger fix because `seq` resets with the bus and would not match turn numbers across runs; (a) is enough to make the description honest. My recommendation: **(a)** now, **(b)** only if a consumer demonstrably needs it.

## GF3 — Blocker: not the source for distribution/dispositions; no truncation counts
**Right.** This is the same root cause as GF1 and GF2: the `decisions` entry describes a *turn-outcome store* that the consumers read, while the code is a *tap that forgets what it wrote*. Corroborated by events.rs: `Contribution.limit: Option<usize>` (line 47) is the **limit**, not a truncation count; `note: Option<String>` (line 49) is free text; there is no `truncated: usize` field anywhere in events.rs. So "truncation counts" in the decision cannot be produced by this schema. The reviewer's specific code points (over-limit replies blocked at turn.rs:127–145; proposals cut to 512 at turn.rs:322–325 with no count) are consistent with a system that records a limit and a reason but not a count.

**Change:** In `decisions`, replace "It holds … the JEV scores and reasons, truncation counts, topic changes and seat availability" with what events.rs can actually back: "It holds every event on the bus with its `seq`, including contributions with their scores, reasons, `limit`, `note` and `accepted` flag; pass/skipped/failed turns; topic changes; seat ready/failed/gone." Remove "truncation counts" unless a `truncated` count field is added to `Contribution` at the point where proposals are cut (turn.rs:322–325). Remove "the append-only source for all three" and replace with "an append-only audit trail of all three; the engine's in-memory state remains the source the prompt builder reads." That sentence alone resolves GF1, GF3 and the ambiguity in GF7.

## GF4 — Major: not every event recorded
**Right on substance, and the code confirms the mechanism.** record.rs:51–53 breaks the loop on `roundtable.ended`, so the recorder task ends there. record.rs:47 drops any event whose `table_of` returns something other than the table (or `None`). Whether `SessionClosed`/`HarnessExited` are published after `roundtable.ended` is an engine/harness fact I cannot verify from these two files, but `TableEnded` is the only end-of-life event in events.rs (line 78) and there is no `SessionClosed`/`HarnessExited` in the schema at all — so those names must come from acp-host, meaning they are published outside this event enum and would still have to route through `table_of` or be dropped by line 47. Both mechanisms are real in the code I can see.

**Change:** the module doc's "every event" must be scoped. Edit record.rs:1–2 to "every event on this bus that carries this table's id, until `roundtable.ended`." Then either (i) make `TableEnded` the last event *published* (shutdown publishes harness events before `roundtable.ended`), so the break is sound; or (ii) remove the break and let the tap end when the bus closes, which is the more faithful "complete record." In the description, `elephant.built` should say "until the table ends" and `gaps` should name shutdown events as known-missing. Note the drop rule at line 47 is a routing requirement, not a bug — but it should be documented (see GF6).

## GF5 — Major: silent write errors; `data: null`
**Right, and this is the only finding with an obvious one-line code fix.** record.rs:50 `let _ = writeln!(...)` discards `Err` from a full disk or closed file with no trace; record.rs:17 `unwrap_or(serde_json::Value::Null)` turns a payload that fails to serialize into a line that looks valid but says nothing. Both directly contradict "complete record."

**Change:** on write error, break the loop and publish a `Notice { level: "error", text: ... }` (or log at error level) so the failure is visible rather than silent; at minimum `eprintln!`. For line 17, replace the silent `Null` with a tagged marker, e.g. `{"data": null, "data_error": "<serialize error>"}`, so a reader can distinguish "no data" from "data lost." Keep the `line` signature. Add a test that a non-serializable payload produces the marker.

## GF6 — Major: undocumented path, schema, routing, readers
**Right.** Everything the reviewer lists is present in record.rs but nowhere in the description: the append+create open (line 42), the filtering rule (line 47), the field set `seq/at_ms/event/data` (lines 14–17), the routing precedence "explicit `table` field wins, else split harness id on `/`" (lines 24–29), and the `{pid, id}` agent-monitor shape (line 34, and the test at 64–70). The description mentions none of it, so a reader cannot tell whether `record.jsonl` is one file per table or one per run.

**Change:** add a short "Storage" section to the description (or a `references` entry pointing at record.rs): path `<ROUNDTABLE_HOME|~/.roundtable>/tables/<id>/record.jsonl`, one file per table; line schema `{seq, at_ms, event, data}`; routing rule as above; append-only so multiple runs to the same table id accumulate into one file. That last point is important and currently undocumented: because the file is opened with `.append(true)`, re-running the same table id does **not** truncate, so `seq` restarts mid-file. Readers must not assume `seq` is unique within a file.

## GF7 — Major: is it a store or an audit trail?
**Right that it is ambiguous; the code resolves it one way.** record.rs never reads. There is no `read`, no `open` for reading, no deserialization of a record line back into a struct. So the record is an **audit trail only**; the prompt builder cannot be reading it (GF1). The ambiguity is purely in the text: `decisions` says "source for all three", `elephant` says "keep a complete record" and "writes every event … including each prompt", which reads like two different components. Resolved by the same edit as GF3: state in `What other parts rely on it for` and in `decisions` that the record is **written, not read**, and that `code.builder.prompt` obtains context from engine memory. If that is not acceptable to the owner, then the code is wrong, not the description, and record.rs needs a read/replay path — but nothing in the current code supports that, so I recommend fixing the description.

## GF8 — Major: undefined terms
**Right.** `JEV`, `disposition`, `veto`, `truncation`, `canonical turn number`, `seat`, `seat availability`, `topic`, `table` all appear in the description with no definition, and several (turn number, seat availability) are also absent from events.rs, so a reader cannot even infer them. **Change:** add a one-paragraph glossary to the description. Cheap, and it removes most of the comprehension findings at once.

## GF9 — Major: opaque audit codes
**Right.** "Run 1 audit E05, E06, D01–D05" and "turn-label drift" are unlinked codes. Nothing in this folder explains them, so the evidence cannot be checked. **Change:** either link the audit document or restate the evidence in plain terms, e.g. "the 2026-11-05 run could not be audited because per-seat context and JEV reasons were not written anywhere; turn numbers drifted because they were per-topic." If the audit document no longer exists, say so.

## GF10 — Nit: location not stated
**Right, and subsumed by GF6.** Calling it a Nit is fair; the fix is the "Storage" section. One file per table under `tables/<id>/`, not one per run.

## GF11 — Nit: vague `gaps`
**Right.** "The request for one message had to be rebuilt" does not say which request, in which format, or why it was needed. **Change:** name the missing artifact (the JEV request payload), say a human reconstructed it by hand from scores and reasons, and list the other known holes (prompt text, shutdown events per GF4). That turns the gap into a specification of what to add.

## GF12 — Nit: undefined map fields and Intent values
**Right.** `role: "SE"`, `name_length: 2`, and `Intent: send/receive` are undefined. `name_length: 2` in particular is meaningless without the convention (two words: "discussion record"). **Change:** define them in the map's own legend, or drop `name_length` if nothing consumes it. Not a code issue.

---

## Summary of edits I recommend
1. Description `decisions`: rewrite from "source for all three" to "append-only audit trail"; remove "canonical turn number" and "truncation counts" (or add the fields). — fixes GF1, GF2, GF3, GF7.
2. Description `elephant.built` + record.rs:1–2: scope "every event" to "this table's events until `roundtable.ended`". — GF4.
3. record.rs: fail loud on write error instead of `let _ =`; tag deserialization failures instead of `data: null`. — GF5.
4. Description: add Storage section and glossary; expand `gaps`; link or restate audit evidence; define map fields. — GF6, GF8–GF12.
