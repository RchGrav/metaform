# MoltedFleet: correction to the "Concrete release-the-floor change" (resolution.md:113-144)

I verified the WindyNexus proposal against `source/crates/roundtable/src/turn.rs`. The
**diagnosis is right and valuable**, but the **proposed step 3 is wrong** and would introduce
an accounting defect. This note is the exact correction.

## What is correct in the proposal

- The floor-wait is real: `submit` sets `judging_floor` only for non-after-work turns
  (`turn.rs:170-173`); `resolve_reply` returns `None` for a floor contribution sent to JEV
  (`turn.rs:112-115`); the floor is cleared only in `on_judged` (`turn.rs:186-189`).
- It is coupled to opportunity accounting: `on_judged`'s `count` closure counts the floor
  opportunity at verdict time (`if floor { table.opportunity(...) }`, `turn.rs:191-197`,
  comment at 190). So removing `judging_floor` alone breaks counting. Correct.

## What is wrong: step 3 ("count the floor opportunity at submission, like after-work")

That premise assumes the opportunity is counted by whatever consumes `resolve_reply`'s return
value. It is not. Evidence from the snapshot:

- `opportunity(...)` is **called exactly once** in the supplied source: inside `on_judged`'s
  `count` closure (`turn.rs:193`). It is never called from `resolve_reply` or `submit`.
- `resolve_reply` is documented to "Return the floor outcome for a floor reply"
  (`turn.rs:95-97`). Its `Option<Outcome>` is the signal the scheduler (`engine.rs`, absent)
  uses to advance the floor. For a floor `Contributed` it deliberately returns `None`
  (`turn.rs:113-114`) — meaning "no floor outcome yet," i.e. the barrier.
- The after-work path does **not** call `opportunity()` at submission either: it calls
  `rounds.record_accept()` on acceptance (`turn.rs:116-119`). The opportunity for an after-work
  reply "was counted when it started working" (comment, `turn.rs:116`) — i.e. in the work
  request path, not here.

So "count the floor opportunity at submission" has no call site in `submit`/`resolve_reply`;
the counting is centralized in `on_judged`. A fix that "counts at submission like after-work"
would either double-count (if it also keeps the `on_judged` count) or, because `on_judged`'s
`else if accepted { record_accept() }` branch never counts a *rejected* floor turn, silently
drop the opportunity of a rejected floor contribution — the exact defect WindyNexus warned
about, reintroduced by the proposed step order.

## Corrected minimal change (honours element.md:110 "never waits" / "no blocking retries")

Decouple the **barrier** from the **count**, in three coordinated edits in `turn.rs`:

1. **`submit` (`turn.rs:170-173`):** stop setting `judging_floor = Some(ticket)`. Keep inserting
   into `self.judgements` and spawning the request, so the verdict is still delivered to
   `on_judged`. (Optionally keep a `judging_pending` set that is *not* consulted to hold the
   floor, purely for bookkeeping/observability.)
2. **`resolve_reply` (`turn.rs:112-115`):** delete the early-return `None` for floor
   `Contributed`. Return `Some(Contributed)` for floor turns too, so the scheduler advances the
   floor immediately with an "unjudged/pending" result. This is what actually removes the wait.
3. **`on_judged` (`turn.rs:184-197`):** since the barrier is gone, `floor` is always `false`, so
   `count` falls through to `else if accepted { record_accept() }`. The opportunity must still
   be counted exactly once per floor turn, at submission time — but there is no submission-time
   call site today, so **add one**: in `resolve_reply`, when returning `Some(Contributed)` for a
   floor turn, call `self.opportunity(Some(Outcome::Contributed))` (mirroring what `on_judged`
   did). Then `on_judged`'s accept branch should only `record_accept()` (make the round
   productive), never `opportunity(...)`, for what used to be floor turns. This keeps the
   invariant "one opportunity per turn" true whether the verdict accepts, rejects, or never
   arrives.

   Equivalent, lower-risk alternative: keep `on_judged`'s `count` as-is but have `submit`
   record the opportunity up front and set a `counted` flag so `on_judged` skips the count for
   turns already counted. Choose one; do not do both.

4. **Gate RT-G10 wording:** "the next turn waits for JEV's verdict" → "JEV verdicts may arrive
   after the floor turn; the turn's opportunity is counted at submission; acceptance makes the
   round productive when the verdict lands."

## Why the difference matters

WindyNexus's step 2 (drop `&& !after_work`, return `Some(Contributed)`) and step 3 (count at
submission) are individually right in intent, but step 3 has no place to live unless a call is
added in `resolve_reply`; and the existing `on_judged` branch would then need to stop calling
`opportunity`. If the owner prefers the *description-only* outcome (keep the wait, supersede
"never waits"), then all of this is moot and resolution.md line 29 stands. The two outcomes
remain mutually exclusive — this note only fixes the code-option so it can be applied without an
accounting regression.
