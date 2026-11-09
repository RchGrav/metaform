# WindyNexus: the concrete code fix for GF3/GF9 (releasing the floor)

The converged `resolution.md` (line 104) records GF3/GF9 as an open owner escalation: "either
release the floor in code (count/share after-work-style, decide on answer) to honour the owner
decision, or formally supersede that decision and keep RT-G10." This note makes the first option
concrete, because it is **not a one-line change** — it depends on how opportunities are counted.

## The load-bearing accounting mechanism

- `resolve_reply` (`turn.rs:110-121`): for a floor contribution sent to JEV, `submit` returns
  `Outcome::Contributed`, and `if outcome == Outcome::Contributed && !after_work { return None; }`
  withholds the floor outcome. After-work turns return `Some(Contributed)` immediately.
- `submit` (`turn.rs:170-173`): `if !judgement.after_work { self.judging_floor = Some(ticket); }`
  — only floor turns install the barrier.
- `on_judged` (`turn.rs:184-197`): the `count` closure is
  `if floor { table.opportunity(Some(...)) } else if accepted { table.rounds.record_accept(); }`.

**Key fact:** the opportunity is counted at *verdict time* for floor turns (via
`table.opportunity(...)`) but at *submission time* for after-work turns (their turn was counted
when work started; `on_judged` only calls `record_accept` on acceptance).

## Why "just remove the barrier" is wrong

If we stop setting `judging_floor` (making `floor == false` for these turns) but keep everything
else, then the `count` closure takes the `else if accepted { record_accept(); }` branch. That is
fine for the *accept* case, but:

1. The opportunity was never counted at submission (it was deferred to `on_judged` via the
   `floor` branch), so a *rejected* floor turn would never count its opportunity at all — the
   turn would be lost from the round accounting.
2. `resolve_reply` returns `None` only when `outcome == Contributed && !after_work`. If we stop
   setting `judging_floor` but leave this line, the floor turn still returns `None` — nothing is
   actually released. Both sides must change together.

## The minimal correct fix

Treat floor contributions exactly like after-work contributions for accounting, and stop blocking:

- In `submit` (`turn.rs:170-173`): delete the `judging_floor = Some(ticket)` and; do not gate
  the floor on the verdict.
- In `resolve_reply` (`turn.rs:112-115`): drop the `&& !after_work` special case so a floor
  contribution returns `Some(Contributed)` immediately, i.e. the floor turn counts as "in flight"
  rather than blocked.
- In `on_judged` (`turn.rs:184-197`): make the `count` closure use the after-work branch
  unconditionally — call `record_accept()` when accepted, and do nothing on rejection. Because
  the floor opportunity is now counted at submission, the verdict only needs to record acceptance,
  exactly as after-work turns already do.
- Update gate RT-G10's wording from "the next turn waits for JEV's verdict" to "JEV verdicts may
  arrive after the floor turn; acceptance is recorded when the verdict lands."

This restores the owner's "the table never waits on JEV" (element.md:110) and "no blocking
retries" while keeping the round-accounting invariant (each opportunity counted exactly once). It
is the minimal change that honours the owner decision without inventing a deadline or a scheduler.

## Why this matters for the resolution

The resolution's "release the floor" is actionable only if the accounting coupling is seen. A
future implementer who simply removes `judging_floor` would silently drop opportunities on
rejection, so the resolution should include this constraint rather than leave it to the owner to
discover. If the owner instead keeps the wait, the description must adopt the floor-sequencing
wording (resolution line 29) and explicitly supersede the "never waits" decision — the two
outcomes are mutually exclusive and both are now specified precisely.
