# FeralSteel — defect list for the final `resolution.md`

The rewrite (170 lines) is a solid document: verdicts are right, GF3/GF8 and GF1/GF7 are merged
correctly, GF10's code trace is exact. Four defects remain; two are regressions from earlier
rounds that the rewrite reintroduced.

## D1 — GF1's chosen fix **widens** the description-code mismatch it claims to close

Section GF1 (lines 18-25) says: "Fix the description, not the code", and the replacement text is
*"When a limit is set, an agent skipped while busy gets the recovery limit (1,024)…"*. That
describes today's `limit_for` — but the very next sentence of the same section, and GF5.1, then
require the code to return `max(base, 1,024)`. Applied together, the new rules[2] is false for
any base above 1,024 (it promises exactly 1,024 where the code gives 5,000) and GF5 records the
code change that makes it false. **Fix:** one sentence must carry `max` too:
*"When a limit is set, a busy skip raises the next discussion reply's limit to 1,024, or leaves
it at the base if the base is larger."* Otherwise GF1 "Accepted" ships a description that GF5's
own patch breaks.

## D2 — GF5.3 ("clear `recovery_due` only for `Activity::Floor`") is back and is dead code

Same defect I raised in turn 3: `recovery_due` is set only in `give_floor`'s not-free branch
(engine.rs:570-575), and every `Reviewing` prompt is offered to an `Activity::Idle` seat
(turn.rs:430-433 from `start_rating`; also `free_to_speak` gate at engine.rs:536-539 whose
`!seat.background` condition is the only way a seat can be skipped-and-free). So no review prompt
can observe `recovery_due == true`; the prescribed edit is unreachable. Worse, it silently
*disagrees* with the previous round's retraction: the writer retracted GF5(c) in prose and
reintroduced its fix in the code section. **Fix:** delete item 3, and add the real lifecycle
statement: recovery is spent **when the prompt is sent** (engine.rs:603-605), so a blocked or
passed recovery reply consumes it. If the team prefers spend-on-share, the edit is in `submit`,
not in `offer`:

```rust
// turn.rs submit(), non-blocked path, after the length test
if self.seats[i].recovery_due { self.seats[i].recovery_due = false; }
```

## D3 — GF9's "recommended follow-up" cannot be implemented as `seat.limit`

GF9 (line 111) recommends "include the current limit in the discussion turn prompt". The only
in-scope value is `seat.limit`, which is assigned **after** `turn_prompt` runs
(engine.rs:597 then 604), so the line would print the previous prompt's limit. Pass the value:

```rust
// engine.rs:596-597
let limit = self.limit_for(i);
let (text, commit) = self.turn_prompt(i, ask, discussion, limit);
// turn.rs: add `limit: Option<usize>` param; for discussion turns,
if let Some(limit) = limit {
    parts.push(format!("Reply limit: {limit} characters; a longer reply is not shared."));
}
```

Note the recovery interplay: because `limit_for` is called here, a *review* prompt with
`recovery_due` would print 1,024 — consistent with reviews being length-checked against that
allowance (turn.rs:126,147). That is fine, and it is why D2 must not be "fixed" by special-casing
reviews.

## D4 — GF11 still says "the chair sets the limit"

Line 132: *"The chair sets the limit in table config"*. The preceding clause contradicts it —
config is host-level (`TableConfig`, config.rs:152-161; no `Command` variant, engine.rs:34-46).
Use: *"The host sets the limit in the table's config; the chair has no command to change it, and
agents cannot."* Then GF6's deletion of the "The chair sets it" comment (rules.rs:7) is the same
edit, not a separate one.

## Two nits worth keeping

- **GF10's line refs are right but the phrase "not retried"** (line 121) should read "the turn is
  not retried; the seat simply gets its next opportunity normally" — the seat is not punished
  beyond the failed opportunity, and `RoundTracker` counts it in `took_part` but not in
  `accepted` (rules.rs:87-93), which is what makes the round unproductive. That detail makes the
  "counts as a Failed opportunity" claim auditable.
- **GF2/GF9 tension:** GF2 rewords the want to *not* promise prompt reporting, while GF9
  recommends the code change that would satisfy the original want. If the team adopts D3's code
  change, keep the **original** want and GF2 stops being a description fix at all. Pick one:
  (a) change the want and skip D3, or (b) do D3 and leave the want. Both are defensible; doing
  both, as the file currently proposes, documents a want the code will then satisfy.

## Verdict

All twelve findings remain Accepted. With D1-D4 and one of the two GF2/GF9 branches, the file is
internally consistent and executable. The root-cause grouping (A: `limit_for`, B: prompt line,
C: recovery lifecycle) is correct, with the caveat that C's item 3 is not a live defect.
