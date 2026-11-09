# SeriousCarbine — independent resolutions for `code.quota.character` (reply limit)

I checked every finding against the four copied sources (`rules.rs`, `config.rs`,
`engine.rs`, `turn.rs`). I agree with the existing `resolution.md` and
`feralsteel-resolution.md` that all twelve findings describe real facts about the
code. My purpose here is to add the points that were either missed or stated too
loosely, because they change *which fix is correct*.

---

## Verdicts (summary)

| Finding | Verdict | Primary action |
|---|---|---|
| GF1 Blocker | RIGHT, but the fix direction needs a decision | code + description, as one change with GF7 |
| GF2 Blocker | RIGHT (re-scope the fix) | code, in `turn_prompt`, not `limit_for` |
| GF3 Blocker | RIGHT | description: supersede 4 decisions |
| GF4 Major | RIGHT (with one qualification) | description |
| GF5 Major | PARTLY RIGHT | description first; only sub-point 1 is a clear code bug |
| GF6 Nit | RIGHT | code + description |
| GF7 Major | RIGHT and it is the same change as GF1 | description |
| GF8 Major | RIGHT | description |
| GF9 Major | RIGHT (consequence of GF2) | code |
| GF10 Major | RIGHT | description |
| GF11 Nit | RIGHT | description |
| GF12 Nit | RIGHT | description |

No finding is simply rejected; **GF5 is the one I qualify**, and **GF1/GF7 must be
resolved together or the fix reintroduces a contradiction**.

---

## A. GF1 + GF7 are one change, and the obvious fix contradicts rules[0]

Fact (verified): `limit_for` (engine.rs:396-399) early-returns on
`let base = self.cfg.base_allowance?;`, so with the default `base_allowance = None`
(config.rs:157-158) the recovery limit is dead. This is a real description/code
mismatch, because the elephant `built` and the owner spec say "one reply after a
busy skip gets 1,024 characters" with no mention of requiring a base limit.

The trap: the natural fix (FeralSteel's `max()` patch, or the first `resolution.md`'s
flat `Some(recovery)`) makes `limit_for` return `Some(1024)` when `base_allowance`
is `None`. On the default table that is **a new restriction**: a reply that was
unlimited becomes capped at 1,024. That directly contradicts two things the
description asserts as current:

- rules[0]: "No reply limit by default (the owner's length experiment)."
- the owner decision "credits removed": "a busy skip earns **one larger reply**".

1,024 on an otherwise-unlimited table is neither "no limit" nor "larger". So the
code fix and the wording fix are not independent; doing the code fix alone makes
GF7's complaint worse, and doing only a wording fix leaves GF1's mismatch.

**Required resolution (both at once):**

1. Code — `limit_for` applies recovery regardless of base, but never shrinks a
   set base:

   ```rust
   pub(crate) fn limit_for(&self, i: usize) -> Option<usize> {
       let recovery = self.seats[i].recovery_due.then_some(self.cfg.recovery_allowance);
       match (self.cfg.base_allowance, recovery) {
           (None, None) => None,
           (base, recovery) => base.into_iter().chain(recovery).max(),
       }
   }
   ```

   Results: no base + no skip = unlimited; no base + skip = 1,024; base 512 + skip
   = 1,024; base 5,000 + skip = 5,000 (never smaller — GF5 sub-point 1).

2. Description — strike "one larger reply" and add an explicit exception to
   rules[0], e.g.: "The default is no limit, **except** that a reply after a busy
   skip is capped at 1,024 characters." Reword rules[2] as: "After a busy skip the
   next discussion reply is limited to 1,024 characters (or the table limit if
   that is larger), once; then normal rules return. This cap applies even when the
   table otherwise has no limit, so it restricts that one reply."

That single pair of edits closes GF1, GF5's compare half, and GF7 coherently. The
owner may prefer the opposite direction (recovery only when a base exists, which is
the current code and which genuinely preserves "one larger reply"); if so, GF1's
fix is a **description** fix, not a code fix. The point is that the two documents
currently commit to the code-fix direction without flagging that it breaks rules[0]
and the owner's "larger" wording. That decision must be made explicitly.

---

## B. GF5's third sub-point is arguably correct behavior, not a defect

GF5 says "review prompts use it up (engine.rs:595, 603-605)". Verified: `offer`
computes `discussion = matches!(activity(0), Floor | Reviewing)`; a review prompt is
`Reviewing`, so `offer` sets `seat.limit = limit` and clears `recovery_due`
(engine.rs:603-605). The recovery really is consumed by a review prompt.

But the description calls the recovery "its **next discussion reply**" (rules[2])
and "each **discussion turn**" (manager want). The code's own definition, in the
`turn_prompt` doc comment (turn.rs:25-26), is: "`discussion`: a floor turn or a
**review**, whose reply is a contribution." And `ask_to_review` (engine.rs:587)
states "Its reply is a contribution". By the project's own vocabulary a review IS
the next discussion reply, so giving it the 1,024 recovery is **consistent with the
written rule**, not a bug. The finding's phrase "use it up" presumes the recovery is
owed to the following floor turn; the description never says that.

**Action:** treat this as under-specification, not a confirmed defect. Either
(a) document "the recovery is consumed by the next discussion prompt, which may be
a review, not necessarily a floor turn" and leave the code alone; or (b) if the
owner intends "next floor contribution", scope the clearing in `offer` to floor
turns only and state it. Do not silently "fix" (b) without that decision — it
changes who gets the larger allowance.

Two related precise facts I did not see stated elsewhere:

- `recovery_due` is cleared **at prompt-send time**, not when a reply arrives
  (engine.rs:603-605 runs inside the `Ok(prompt)` branch of `offer`). So "once"
  means "one discussion prompt is issued with the recovery limit", regardless of
  whether that reply is accepted, a `Pass`, `Empty`, or itself blocked. A recovery
  reply that is blocked does **not** earn a second 1,024 attempt. The description
  should say this.
- The flag is consumed **only** by discussion (Floor/Reviewing) prompts. A
  Proposing, Rating or Notified prompt also calls `limit_for` (engine.rs:596) but
  does not update `seat.limit` or clear `recovery_due` (the `if discussion` guard),
  so the recovery survives those prompts. That is sensible and should be stated as
  the rule rather than left implicit.
- On `give_floor` vs `on_tool`: `give_floor` sets `recovery_due` (engine.rs:573)
  when a seat is already busy as its turn arrives; `on_tool` (engine.rs:670-676)
  does not set it when a floor turn turns into work. Both record
  `Outcome::SkippedWorking`. Whether the second path is a "busy skip" is genuinely
  ambiguous: in `on_tool` the agent **already had the floor**, and its eventual
  after-work reply is length-checked against the `seat.limit` fixed at the start of
  that floor turn (turn.rs:126 uses `self.seats[i].limit`), so a `recovery_due` set
  there would only affect the *following* floor turn, not the current reply. The
  description must define "busy skip" (does it include work that starts after the
  floor was granted?) before this can be called a code bug.

---

## C. GF2 / GF9: re-scope the fix (the computation is fine; the prompt is not)

Verified: `turn_prompt` (turn.rs:31-83) adds the round line, notices, prior
messages and `ask`; the doc comment (turn.rs:22-23) still promises "then the
characters line (O)" but no code emits it. `FloorGiven` carries `allowance:
seat.limit` (engine.rs:611) but that is a bus event for the host/chair, not text the
agent sees.

The important scoping point: the reply-limit element **does** compute and expose
the allowance — `limit_for` (engine.rs:396), `seat.limit` (engine.rs:604), and the
`FloorGiven`/`Contribution.limit` fields. What is missing is purely that
`turn_prompt` does not print it. So the fix belongs in `turn_prompt` (append a
"Reply limit: N characters; a longer reply is not shared" line when `seat.limit`
is `Some`), **not** in `limit_for` or the data model. GF9 ("how an agent learns the
limit before being blocked") is the same fix; an agent cannot comply with a limit
it is never told. Note the line must also go on `ask`-based discussion prompts
(reviews), because those replies are length-checked too (turn.rs:126, 147).

---

## D. GF4 / GF10: one qualification and the exact "becomes" answer

Verified: `truncate_to` (rules.rs:23-38) is still used for topic proposals at
`PROPOSAL_LIMIT = 512` (turn.rs:322-323, rules.rs:19), so "never cut" is false for
proposals. A blocked reply returns `Outcome::Failed` before any `Judgement` is
built (turn.rs:128-146), so JEV is never invoked.

Qualification: for a **floor** reply the `Failed` outcome is recorded via
`opportunity(Some(Failed))` (engine.rs:699-701 → `rounds.record`). For an
**after-work** reply (`after_work = true`) `resolve_reply` returns `None`
(turn.rs:121 `(!after_work).then_some(outcome)`), so no *new* Failed opportunity is
recorded — the opportunity was already counted as `SkippedWorking` when work began.
"A blocked reply counts as a Failed opportunity" is therefore exact only for floor
replies; the description should say "the floor turn is failed; an after-work reply
does not add another opportunity".

What a blocked message becomes (the GF10 answer, to put in the rules): a
`Contribution` event with `id: None`, `accepted: false`, `judged: false`, and
`reasons: ["over the limit: {length} of {limit} characters"]` (turn.rs:132-144);
the length check runs **before** and **instead of** JEV; the author is told via
`seat.notices.push(prompts::too_long(...))` (turn.rs:131), delivered only at its
next **discussion** turn (turn.rs:52-55; `commit` clears notices only for
discussion, turn.rs:88-90) — so a Proposing/Rating/Notified prompt does not deliver
it. "When the author is told" = next discussion turn, not immediately.

---

## E. The remaining findings (confirmed, briefly)

- **GF3 / GF8** — RIGHT. `Seat` (engine.rs:77-103) has only `limit` and
  `recovery_due`; no bank. `submit` blocks (turn.rs:128-146). Decisions "veto",
  "accepted contribution", "topics", "characters" describe the removed scheme and
  are not in `superseded`. Move them to `superseded`. State the unit once: length =
  Unicode scalar values (`text.chars().count()` at turn.rs:129); proposals are cut
  at a grapheme boundary (rules.rs:29-36) so no grapheme is split; the block check
  counts scalars and does not cut. The "characters" decision conflates the two
  operations; retire it and keep one active statement.
- **GF6** — RIGHT. `DEFAULT_BASE = 512` (rules.rs:7-8) is referenced nowhere
  (grep confirms only its definition) and its "Default reply limit" comment
  contradicts the `None` default. Delete it. Document the validation invariant
  (config.rs:113-115): `base_allowance == Some(0)` and `recovery_allowance == 0`
  are rejected; limits are at least 1. Note `recovery_allowance` is a plain `usize`
  with no "unlimited" value — it is always a positive number even on a no-base
  table.
- **GF11** — RIGHT. Both limits are `TableConfig` fields set at table creation
  (config.rs:154-161); the chair cannot change a running table's limit (no
  `Command` variant does) and agents cannot (rules.rs:7, config.rs:156). "The
  owner's length experiment" is unexplained — replace with "No limit by default
  (owner, 2026-11-07)."
- **GF12** — RIGHT. The run-1 investigation note "the current spec truncates
  instead" is stale (the rule now blocks). "Bank", "session mode", "busy skip" are
  undefined; define "busy skip" (see B) and mark the bank/session-mode vocabulary
  as belonging to the superseded scheme. The README 4.x references appear to
  describe the old truncation/credit scheme; re-scope or mark them historical.

---

## Net: code fixes vs description fixes

- **Code:** `limit_for` (GF1, GF5-compare, GF7 — with the rules[0] caveat in A);
  print the allowance line in `turn_prompt` for discussion prompts incl. reviews
  (GF2, GF9); delete `DEFAULT_BASE` (GF6).
- **Description:** supersede the four bank-era decisions and re-scope README 4.x
  (GF3, GF8, GF12); fix the run-1 note (GF12); "never cut" is discussion-replies
  only + blocked = failed floor turn, skips JEV, author told next discussion turn
  (GF4, GF10, with D's qualification); who sets the limit (GF11); the rules[0]
  exception and the death of "one larger reply" (GF1/GF7); define "busy skip" and
  the recovery's consumption semantics (GF5, B).
- **Owner decision required before coding:** does 1,024 after a skip apply on a
  no-limit table (a restriction), or only when a base limit exists (the current
  code, which preserves "one larger reply")? This decides whether GF1 is a code
  fix or a description fix, and whether a review prompt should consume the recovery.
