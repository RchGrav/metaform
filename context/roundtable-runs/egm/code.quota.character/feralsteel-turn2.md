# FeralSteel — review of `resolution.md` (turn 2)

The shared `resolution.md` confirms all twelve findings. I agree with the direction, but three
parts of it **contradict the code as written** and should not ship.

## Correction 1 — GF5/GF7: reviews cannot eat recovery (the .md says they can)

`resolution.md` GF5 sub-point 3 and my own turn-1 note both assume a review prompt calls
`limit_for` while `recovery_due` is set. It cannot, for two independent reasons:

1. **A skipped seat is busy.** `give_floor` sets `recovery_due` only on the `else` branch of
   `free_to_speak(i)` (engine.rs:570-575), i.e. only when the seat is not free. `ask_to_review`
   runs only inside `start_rating`'s `if self.seats[i].activity == Activity::Idle` loop
   (turn.rs:430-433) and `settle_results`/`settle_poll` require `Activity::Idle`. So no review,
   proposal or results prompt can reach a seat while its recovery is due.
2. **`offer` clears it before any discussion prompt is sent** — including the review. In `offer`
   the order is `limit_for(i)` (engine.rs:596) → `turn_prompt` → `commit` → `seat.recovery_due =
   false` (engine.rs:603-606). The review reply is measured against `seat.limit` set from that
   same call, so it *does* get the recovery allowance, but nothing else can steal it first.

So the real GF5 defect is narrower than both drafts claim: the recovery is assigned when the
prompt is *sent*, and spent even if the reply is blocked (`submit` returns `Failed` at
turn.rs:145 and never re-arms it) or if the agent passes. That is defensible ("one reply") but
must be *stated*. **Do not implement the "only clear on Floor" suggestion** in GF5(c) — with the
current `free_to_speak` gate it is a no-op, and the review-uses-the-allowance behaviour is what
makes a recovery reply judgeable.

**Fix for GF5(b) instead — the floor-to-work skip really does miss recovery:**
`on_tool` (engine.rs:667-676) turns a Floor into Working and calls
`opportunity(SkippedWorking)` without setting `recovery_due`. A busy seat re-skipped later does
get it (engine.rs:573), so the omission only bites an agent that is never skipped again. Set
`recovery_due = true` in `on_tool`'s `Activity::Floor` arm, next to `worked_in_topic = true`.

## Correction 2 — GF1/GF7: "no base ⇒ no recovery" may be intentional

`limit_for` (engine.rs:396-399) reads as a deliberate composition: *recovery refines a limit, it
does not impose one*. Both drafts call it a Blocker bug. That is a defensible reading of the
owner's words, but it is not the only one, and the element owns no decision for it. The two
candidate semantics give different behaviour on the default config:

| config | today | "recovery stands alone" | "max(base, recovery)" |
|---|---|---|---|
| no base, skip | unlimited | 1,024 | 1,024 |
| 512, skip | 1,024 | 1,024 | 1,024 |
| 5,000, skip | **1,024** (shrinks) | 1,024 (shrinks) | 5,000 |

The `5,000` row is the only unambiguous defect: the owner's word is *larger*, so a recovery must
never shrink an allowance. That alone justifies `max`. Whether an otherwise-unlimited table
should retroactively impose 1,024 needs an owner decision, and should be recorded in
`decisions` rather than silently encoded. My proposed `limit_for` from turn 1 already implements
the `max` column and answers the "stands alone" question with *yes*; either row 1 or row 2 needs
an entry in `decisions` (e.g. "a busy skip bounds an unlimited reply at 1,024").

## Correction 3 — GF6 vs GF11: dead constant is not licence to say "chair sets it"

`resolution.md` GF11 says "the chair sets it" citing rules.rs:7 and config.rs:156 — the doc
comments of the dead `DEFAULT_BASE`, the very thing GF6 wants deleted. `TableConfig` is fixed at
construction (config.rs:152-161); no event in `engine.rs` (lines 20-45) changes a limit. The
code comment "The chair sets it; agents cannot" is aspirational, not implemented. Keep the
accurate claim: *the host sets both limits when the table is created; nobody can change them
during a table.* Deleting `DEFAULT_BASE` and removing that sentence are the same edit.

## Points the shared resolution should also add

- **The block notice never reaches the author's prompt twice.** `push(prompts::too_long(...))`
  (turn.rs:131) lands on `seat.notices`, drained only on a `discussion` turn (turn.rs:52-55) and
  cleared by `commit`. A seat blocked on a review reply therefore waits for its next floor turn;
  a seat blocked on its own floor turn sees it on the *following* turn. Worth one sentence in
  rules, since GF10 asks "when is the author told".
- **`truncate_to` is cited by the block path?** No — `submit` (turn.rs:125-146) uses
  `text.chars().count()`, not `truncate_to`. So removing the "characters" decision does not
  delete `truncate_to`; it stays solely for proposals (turn.rs:323).
- **GF2 (b) is the only behaviour-preserving description fix that keeps agents compliant.** If we
  choose (a) instead (weaken the want), then in the limit-set configuration every long reply is a
  silent failed turn. The shared resolution hedges; I recommend (b) — one line in `turn_prompt`
  when `seat.limit.is_some()`, for both floor and review prompts.
- **`review` prompts and GF4:** `ask_to_review`'s comment claims the *final allowance line*
  applies to reviews (engine.rs:587), which is false today (no such line). Confirms GF2.
