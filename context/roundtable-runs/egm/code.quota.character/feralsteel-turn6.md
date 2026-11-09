# FeralSteel — final audit of `resolution.md` (turn 5 → 6)

Verdicts: unchanged, all twelve **Accepted**. The four structural corrections (A, B, C) are now
in the right places. Two spec bugs remain, plus one place where the doc over-claims the fix.

## E1 — The `limit_for` snippet is a no-op and hides the real base-above-1,024 bug

Lines 30-41:

```rust
base.map(|b| b.max(self.cfg.recovery_allowance)).filter(|_| base.is_some())
```

`base.map(...)` is already `None` when `base` is `None`, so the `.filter` changes nothing (with
`Option::is_some` the filter only removes `None`, which the map already produced). It is dead
guard code, not "the one-line switch": removing the `.filter` does not turn recovery on. The
switch it claims to expose is not the switch that exists.

Also, and more importantly, the snippet **breaks the one case the file calls unambiguous**: for
recovery with no base, the doc's `GF1` text says "the owner question is left visible", but
`GF5` and `GF7` both require recovery never to shrink an allowance and this snippet returns
`None`. Then line 46 says "base 5,000 → 5,000". To get the no-base switch, the code must read:

```rust
pub(crate) fn limit_for(&self, i: usize) -> Option<usize> {
    let base = self.cfg.base_allowance;
    let recovery = self.seats[i].recovery_due.then_some(self.cfg.recovery_allowance);
    // Owner decision: delete `.filter(|_| base.is_some())` to let a busy skip bound an
    // otherwise-unlimited reply at the recovery limit.
    base.into_iter().chain(recovery).max().filter(|_| !self.seats[i].recovery_due || base.is_some())
}
```

which is still ugly — and the ugliness is the point: the file should state that the no-base
question is genuinely two code shapes, not one shape with a removable filter. Simpler and
honest:

```rust
if self.seats[i].recovery_due {
    match base {
        Some(base) => Some(base.max(self.cfg.recovery_allowance)),
        None => None, // OPEN owner decision; change to Some(self.cfg.recovery_allowance) to cap
    }
} else { base }
```

One line changes, one `None` becomes `Some(...)`, and no `.filter` describes a decision it does
not make.

## E2 — "Spend recovery in `submit`" is in the wrong function for the recovery reply

Root cause C, lines 93-98, says: remove `seat.recovery_due = false` from `offer`, and clear it
in `submit` after the length check. But `submit` is only reached on `Reply::Contribution`
(turn.rs:110). Consider the reply kinds that actually follow a busy skip:

- **Blocked** → `submit`, returns `Failed` (turn.rs:130-146): stays armed with the patch. Correct.
- **Pass** → `resolve_reply` classifies `Reply::Pass` (turn.rs:99-103) and never calls `submit`:
  the flag would stay armed forever. Pass is the *common* post-skip reply, so the patch as written
  leaves a stale recovery that fires on a later, unrelated turn.
- **Sent after work** (`after_work` true, turn.rs:110): `submit` runs normally, fine.

So the clear belongs at the end of `resolve_reply`, not in `submit`:

```rust
pub(crate) fn resolve_reply(&mut self, i: usize, reply: &str, after_work: bool) -> Option<Outcome> {
    let outcome = match rules::classify(reply) {
        Reply::Pass => { /* publish */ Outcome::Passed }
        Reply::Empty => { /* publish failed */ Outcome::Failed }
        Reply::Contribution(text) => self.submit(i, &text, after_work),
    };
    // Spend recovery on any reply that is not blocked (a block re-arms it for the next turn).
    if !matches!(outcome, Outcome::Failed) || !self.seats[i].recovery_due {
        // ...
    }
    ...
}
```

in practice: clear on `Passed` and on `Contribution`, keep on the *blocked* `Failed` only. But
"keep on Failed" is ambiguous because `Failed` also means empty reply. Cleanest: have `submit`
return an explicit `Blocked` marker, or check `self.seats[i].limit.is_some_and(|l| reply_len >
l)` before deciding — otherwise an empty reply silently re-arms recovery, which the doc does not
claim and the file's own GF10 trace ("blocked → Failed") cannot distinguish. **The doc must pick
one: recovery is spent on any reply except a *blocked* one, and `Failed` from an empty reply
counts as spent.** That requires the `Outcome` distinction or a length recheck; say which.

## E3 — GF2/GF9 now contradict each other in the final text

Lines 83 and 143 say the allowance line is *added to the prompt* (root cause B). But the
turn-4 defect list's "two nits" (GF2/GF9 tension) still stands unaddressed in this revision: the
want `code.builder.prompt` can now stay as written ("Tell the participant how many characters it
may contribute"), since B implements it. Line 155's closing sentence should therefore say the
want is *satisfied by code*, not that GF2 is a description fix. Under the current text a reader
sees GF2 listed as "Right/Blocker — B: add allowance line" and then the file says to "update the
want" — those are two different actions on the same sentence. Pick one: the file already chose
code, so drop the "update the want" instruction.

## E4 — minor: GF10's "skips JEV permanently"

Line 108 says "skips JEV" and the summary says "skips JEV" — fine. But note the seat still
consumes a full opportunity and `RoundTracker::record` increments `took_part` while
`accepted` stays zero (rules.rs:87-93); that is what pushes `nonproductive_streak`. The GF10 fix
text should say "counts toward the round's nonproductive streak" rather than only "Failed
opportunity", because the observable consequence (two quiet rounds → topic advance / table end,
engine.rs:647-656) follows from that counter, not from the label `Failed`.

## Verdict

The document's verdicts and root-cause structure are correct and the residual items are all
mechanical. With E1 (honest two-shape `limit_for`), E2 (clear recovery in `resolve_reply`, not
`submit`, and define the empty-reply case), E3 (drop the "update the want") and E4 (name the
counter), the file is internally consistent. No finding is rejected; all twelve Accepted.
