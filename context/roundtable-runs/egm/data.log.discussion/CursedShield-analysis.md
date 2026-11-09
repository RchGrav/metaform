# CursedShield — analysis of findings for `data.log.discussion`

I am the independent participant CursedShield. Below is my verified assessment.
**Scope note:** the `source/` folder in this workspace contains only `record.rs` and
`events.rs`. Several findings cite `turn.rs`, `engine.rs`, `app.rs`, `tables.rs`, and
`acp-host/src/harness.rs`, which are **not present** in this workspace. I mark each finding
as **verified** (confirmable from `record.rs`/`events.rs` alone), **partially verified**
(confirmable for the part in the provided files, but the cited outside file is absent), or
**unverified** (rests entirely on an absent file).

## Verified from `record.rs` / `events.rs` directly

- `record.rs:17` — `"data": envelope.to_json().unwrap_or(serde_json::Value::Null)`.
  Unserializable payloads are written as `data:null`. **Confirms GF5 (second half).**
- `record.rs:50` — `let _ = writeln!(file, "{line}")`. Write errors are discarded.
  **Confirms GF5 (first half).**
- `record.rs:51-53` — `if envelope.name == "roundtable.ended" { break; }`. The recorder
  stops at `roundtable.ended`; any later event (SessionClosed / HarnessExited) is never
  written. **Confirms GF4 (first half).**
- `record.rs:47` — `if table_of(&line["data"]).as_deref() != Some(table.as_str()) { continue; }`.
  Events whose table cannot be resolved are silently dropped. **Confirms GF4 (second half).**
- `events.rs:51` — `event!(Passed, "roundtable.pass", { seat: String });` — no number.
- `events.rs:54` — `event!(Skipped, "roundtable.skipped", { seat: String, reason: String });` — no number.
- `events.rs:39-50` — `Contribution` carries `id: Option<String>`, `limit: Option<usize>`,
  `reasons: Vec<String>`, `scores`. There is **no truncation count** and **no canonical turn
  number**. **Confirms GF2 (Pass/Skipped carry no number) and GF3 (no truncation count).**
- `events.rs` has **no event carrying the prompt text an agent received**. The event set is
  about what agents *did* (Contributions, Passes, Topics, Chair, Ratings, Notices). This
  directly contradicts the elephant layer's "including each prompt text" claim. **Confirms
  GF1/GF7 at the event-schema level.**

## Per-finding verdicts

| # | Severity | Verdict | Basis |
|---|----------|---------|-------|
| GF1 | Blocker | **RIGHT** | record.rs is append-only; no read interface exists for the prompt builder. The event set never carries a received prompt. Which source the prompt builder actually reads (turn.rs:54-66) is outside the provided files, but the record clearly cannot supply prompt content. |
| GF2 | Blocker | **RIGHT** | events.rs confirms Pass/Skipped carry no number; Contribution.id is Option<String> (may be None). "Canonical turn number" is not in the event schema. |
| GF3 | Blocker | **RIGHT** (partially verified) | No truncation count in the event schema; Contribution has only `limit`/`reasons`. Whether the record is "the source for distribution/dispositions" cannot be confirmed from these files; engine memory claims are unverified. |
| GF4 | Major | **RIGHT** | Fully verified: recorder stops at roundtable.ended; unresolvable-table events dropped. |
| GF5 | Major | **RIGHT** | Fully verified: write errors discarded; unserializable → data:null. |
| GF6 | Major | **RIGHT** | The described path/schema/routing/readers are absent from element.md. `record.rs` does contain a schema and routing logic that the description never documents. |
| GF7 | Major | **RIGHT** | decision vs elephant layers describe different roles; the ambiguity is real and the prompt-builder-read question is unresolved. |
| GF8 | Major | **RIGHT** | Terms (JEV, disposition, veto, truncation, canonical turn, seat, seat availability, topic, table) are used but undefined. |
| GF9 | Major | **RIGHT** | `E05, E06, D01-D05` and "turn-label drift" are opaque, unlinked codes. |
| GF10 | Nit | **RIGHT** | Location of record.jsonl not stated anywhere in element.md. |
| GF11 | Nit | **RIGHT** | "Request had to be rebuilt" is vague and sits uneasily against "complete record". |
| GF12 | Nit | **RIGHT** | role, name_length, Intent values undefined. |

## The core tension the resolution must state

The **decision** layer claims the record is *the source* for distribution/dispositions/context;
the **elephant** layer claims it is a *complete event log of every prompt and reply*. Both
claims fail against the actual code:

1. `record.rs` is a passive append-only writer with no read path — it cannot be "the source"
   for anything the prompt builder does.
2. The event schema never records a received prompt, so "every prompt" is false.
3. The recorder is lossy by design (stops at `roundtable.ended`; drops unresolvable-table
   events; discards write errors; nulls unserializable payloads), so "every event / complete"
   is false.

I recommend the resolution state: the record is an **append-only audit/telemetry trail, not a
functional source**, and the description should be corrected to say so, with the lossy
characteristics documented.
