# FeralSteel — final check of `resolution.md` (turn 4)

The revised file now carries the right verdicts and two of my three corrections. Three residual
items, all small:

## 1. GF1's recommended fix lands in the wrong branch

`resolution.md` lines 36-47 keep the `recovery_due` branch returning 1,024 regardless, and call
the no-base case "deferred pending the owner decision". But the deferred outcome is already
*inside* that snippet: with `base_allowance = None`, `unwrap_or(0)` makes line 39 return
`Some(1_024)`. So the file simultaneously (a) says no-base is undecided, and (b) ships code that
decides it. Make the two branches explicit so the open question is a one-line switch:

```rust
pub(crate) fn limit_for(&self, i: usize) -> Option<usize> {
    let base = self.cfg.base_allowance;
    let recovery = self.seats[i].recovery_due.then_some(self.cfg.recovery_allowance);
    // OPEN: delete the `.filter` to let a busy skip bound an unlimited reply (owner decision).
    base.into_iter().chain(recovery.filter(|_| base.is_some())).max()
}
```

The base>1,024 fix (`max`) is unaffected by the filter: base `Some(5_000)` passes it, so the
result is 5,000. Only the no-base row changes. This makes the deferred decision genuinely
deferred instead of frozen in the snippet.

## 2. GF5(c)'s retraction note cites the wrong call chain

Line 72 says `ask_to_review` "is called only on a free agent (engine.rs:541-544, on the lone free
agent)". Two callers exist and the reviewer's real hazard is the second: `start_rating`
(turn.rs:430-433) and `settle_results` (turn.rs:555) both call `offer` directly for seats gated on
`Activity::Idle`. The claim still holds, but only because of that idle gate — not because
`ask_to_review` is special. Reword to "every review/rating/results prompt requires
`Activity::Idle` (turn.rs:430-433, 555, 294-302), and `recovery_due` is set only for non-idle
seats (engine.rs:570-575); the two cannot overlap." As written, a reviewer re-checking
engine.rs:541-544 will find `free_to_speak`'s `!seat.background` condition and think the hazard is
live for background-busy agents — which `free_to_speak` does allow, but `recovery_due` is set
only in the *not* `free_to_speak` branch, so the same argument still holds. Simpler citation is
better.

## 3. Root cause B still needs the ordering fix (unresolved from turn 3)

Line 60 says the line comes "from `seat.limit`". `turn_prompt` is called at engine.rs:597 and
`seat.limit = limit` is assigned at engine.rs:604 — after. So a line reading `seat.limit` shows
the *previous* turn's limit on the first limited turn (and `None` on the first turn of the table
if no base default is set at `Table::new`, engine.rs:316, where it may still be the base — but
after a recovery turn it is stale). Pass `limit` into `turn_prompt` explicitly:

```rust
// engine.rs:597
let (text, commit) = self.turn_prompt(i, ask, discussion, limit);
// turn.rs turn_prompt signature
pub(crate) fn turn_prompt(&self, i: usize, ask: Option<String>, discussion: bool, limit: Option<usize>) -> (String, Commit)
// inside, after the round line and before notices:
if discussion && let Some(limit) = limit {
    parts.push(format!("Reply limit: {limit} characters; a longer reply is not shared."));
}
```

## Final verdict on the file

All twelve findings Right: I agree. The two-root-cause synthesis is correct, and GF2/GF9 and
GF1/GF7 clusters are irreducible without code changes. With the three edits above, the file is
executable and the open owner question (does a busy skip bound an unlimited reply) is visibly a
decision rather than a hidden constant.
