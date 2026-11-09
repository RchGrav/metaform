# FeralSteel — patch notes for `resolution.md` (turn 3)

The rewritten `resolution.md` adopts the root-cause framing and is broadly right. Two of its
prescriptions are still not executable as written; both are fixable with small edits.

## Defect 1 — "clear `recovery_due` only on a Floor prompt" is unreachable dead code

`resolution.md` Root cause C, first bullet, says to keep `seat.limit` on review prompts but not
clear `recovery_due` there, "so a review does not consume it". In the current code that branch can
never run: a seat is given a review only when it is `Activity::Idle` (turn.rs:430-433,
`settle_results` turn.rs:555), and `settle_poll`/`give_floor` only set `recovery_due` for seats
that are *not* idle (engine.rs:570-575, turn.rs:294-302). So `recovery_due == true` implies the
seat is busy, and every review/proposal/results prompt requires idle. The review-consumes-recovery
hazard is therefore **latent, not live** — the same conclusion as my turn-2 note, which the
rewrite kept in its text but then prescribed a fix for.

**Action:** drop the "clear only on Floor" change. Replace it with the one real lifecycle rule:

```rust
// turn.rs submit(), on the non-blocked path (after the length test at turn.rs:130-146)
if self.seats[i].recovery_due { self.seats[i].recovery_due = false; }
```

i.e. spend recovery when a *shareable* reply is produced, not when the prompt is sent. Today
`offer` clears it (engine.rs:603-605) so a **blocked or passed** recovery reply silently burns the
allowance. State that choice in the description either way (spent on send vs spent on share);
otherwise GF5/GF10 remain untestable.

## Defect 2 — the GF1 code block does not compile-cleanly and misorders the comparison

`self.cfg.recovery_allowance.max(self.cfg.base_allowance.unwrap_or(0))` happens to be right for
`usize`, but `unwrap_or(0)` signals "no base" as 0 — and `base_allowance == Some(0)` is rejected by
`validate` (config.rs:113-115), so 0 is a safe sentinel only by accident. `Option::max` over the
two candidates states the intent directly and keeps `None` meaningful:

```rust
pub(crate) fn limit_for(&self, i: usize) -> Option<usize> {
    let base = self.cfg.base_allowance;
    let recovery = self.seats[i].recovery_due.then_some(self.cfg.recovery_allowance);
    base.into_iter().chain(recovery).max()
}
```

Still equivalent behaviour (no base → 1,024 on skip; 512 → 1,024; 5,000 → 5,000) but no magic
zero. If the roundtable prefers the flat form, keep `max` but write
`self.cfg.base_allowance.unwrap_or(self.cfg.recovery_allowance)` — wrong when base < recovery, so
prefer the `Option` version.

## Defect 3 — GF11 still cites the deleted constant

Root cause text and GF11 point to `config.rs:156, rules.rs:7` as the source for "who sets the
limit". rules.rs:7-8 is `DEFAULT_BASE`, which GF6 deletes; config.rs:156 is a doc comment, not a
mechanism. The mechanism is `TableConfig` construction. Cite config.rs:152-161 only, and delete
"the chair sets it" wherever it survives (rules.rs:7 comment, engine.rs:587 comment).

## Small confirmations worth keeping in the final file

- **GF10 evidence is exact.** Blocked path: `submit` returns `Outcome::Failed` at turn.rs:145
  *before* `Judgement` is built (turn.rs:147), so JEV is genuinely skipped; the reason string
  "over the limit: {length} of {limit} characters" (turn.rs:140) is the only machine-readable
  trace, plus `limit: Some(limit)` on the `Contribution` event (turn.rs:141).
- **Root cause B line placement matters.** `turn_prompt` is called before `seat.limit` is set
  (engine.rs:597 vs 604), so the allowance line cannot read `seat.limit` — it must be passed the
  `limit` computed at engine.rs:596, or `seat.limit` must be set first. As written ("backed by
  `seat.limit`") the patch would print the *previous* turn's limit. Concretely:

```rust
// engine.rs offer(), inside the discussion branch of turn_prompt
if discussion && let Some(limit) = limit {
    parts.push(format!("Reply limit: {limit} characters; a longer reply is not shared."));
}
```

and pass `limit` into `turn_prompt` as a parameter.

Net: the shared file needs three edits — delete the dead review-clear instruction, swap the
`limit_for` snippet for the `Option::max` form, and fix GF11's citations plus the
`seat.limit`-ordering bug in Root cause B. With those, all twelve verdicts stand as Right and the
two-root-cause framing is sound.
