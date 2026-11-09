# FeralSteel — resolutions for reply limit (with patch text)

This is my working instrument: for each finding, verdict, then the concrete edit to `element.md`
or the source. It is meant to be lifted into `resolution.md`. Line references are to the `source/`
copies.

## Key semantic that most findings hinge on

`limit_for` returns `None` whenever `base_allowance` is `None` (engine.rs:396-399). So today the
recovery limit is dead in the default configuration, and `recovery_allowance` only ever *replaces*
the base rather than bounding it. Both GF1 and GF5/GF7 are facets of this one bug. The fix is to
compose the two concerns separately:

```rust
// engine.rs:394-399 — replacement
/// The limit for this seat's next discussion prompt: the table's reply limit, or the recovery
/// limit once after a busy skip. Recovery applies even with no base limit. When both apply the
/// larger wins, so a busy skip never gives less room than a normal turn (owner's spec).
pub(crate) fn limit_for(&self, i: usize) -> Option<usize> {
    let recovery = self.seats[i].recovery_due.then_some(self.cfg.recovery_allowance);
    match (self.cfg.base_allowance, recovery) {
        (None, None) => None,
        (base, recovery) => base.into_iter().chain(recovery).max(),
    }
}
```

Consequence: with no base limit and a skip, the seat gets exactly 1,024 for that reply (the
"register" of the owner's experiment). With base 512+recovery 1,024 → 1,024. With base 5,000 +
recovery 1,024 → 5,000 (never smaller). This matches every natural reading of "one larger reply"
and of "1,024 is plenty".

## GF1 (Blocker) — recovery limit is dead by default
**Right.** `limit_for` short-circuits on `None` base; default `base_allowance` is `None`
(config.rs:157-158); tests only set a base (tests/engine.rs:32) so the hole is invisible.
**Change:** the `limit_for` patch above (code), and rule[2] must say "1,024 applies even when no
base limit is set".

## GF2 (Blocker) — builder cannot report the allowance
**Right.** `turn_prompt` (turn.rs:31-83) builds round line, notices, messages, `ask`; the old
characters line is gone. Allowance only reaches the bus via `FloorGiven` (engine.rs:611).
**Change:** either (a) description fix — weaken the `code.builder.prompt` want to "the chair
reports the allowance to the UI, not to the prompt"; or (b) code fix, the cleaner one, since
agents will be silently blocked: append a line in `turn_prompt` when `seat.limit` is `Some`:
`Reply limit: {N} characters; a longer reply is not shared.` Also add it to prompts with
`ask` (review) because reviewing replies are length-checked too (turn.rs:126,147). I recommend
(b) + keep the want as written.

## GF3 (Blocker) — decisions describe a removed bank
**Right.** decisions 2-5 (accepted contribution, topics, characters veto) describe a bank and
grapheme truncation. Code has no bank (engine.rs:83-86 is just `limit`/`recovery_due`) and
blocks (turn.rs:128-146). They are not in `superseded`.
**Change:** move those four decisions from `decisions` to `superseded` with rule text, e.g.
"An accepted contribution spends the bank and the allowance returns to 512", "The allowance
bank carries across topic changes", "Length is counted in Unicode scalars and cut at grapheme
boundaries". Keep the 'veto' decision only as superseded too, since non-sharing of a vetoed
message is now the *general* block rule, not a bank rule.

## GF4 (Major) — "never cut" ignores proposals; blocked reply is a failure
**Right on both.** `truncate_to` (rules.rs:19-38) is still used for topic proposals
(turn.rs:323), so "never cut" is false as stated. A blocked reply returns `Outcome::Failed`
(turn.rs:145) and is not submitted to JEV (turn.rs:128, returns before `Judgement`).
**Change (description):** amend rule[1] to "A discussion reply over the limit is blocked, never
cut; topic proposals are still cut to 512. A blocked reply counts as a failed turn and is not
sent to JEV." Optional code change: also block proposals instead of cutting, but that is a
different element (`topic poll`), so I'd rather make the description precise than change code we
don't own here.

## GF5 (Major) — recovery replaces base; give_floor doesn't clear it
**Right on the replace problem** (fixed by the `max` in the patch). **Right on the second half
too:** `offer` clears `recovery_due` only for `discussion` activities (engine.rs:603-606);
`give_floor` (engine.rs:573) sets it, while floor-to-work via `on_tool` (engine.rs:670-676)
does not clear it and its `SkippedWorking` opportunity does not consume a discussion turn.
A review prompt (engine.rs:595) *is* `discussion`, so it *does* consume the recovery — that part
of the finding is correct and is a real defect: a review request can eat the recovery the agent
needs for its next contribution.
**Change:** treat recovery as a property of the next *discussion contribution that gets
length-checked*, not "the next prompt": set it in `give_floor` and clear it in `submit` when a
non-blocked contribution is accepted (or, minimally, in `offer` only when `discussion && !ask`).
Also document that a recovery reply that is itself blocked has spent it.

## GF6 (Nit) — dead DEFAULT_BASE, undocumented 0 rejection
**Right.** `DEFAULT_BASE = 512` (rules.rs:7-8) is unused and contradicts the comment "No limit
is the building mode"; validation rejects 0 (config.rs:113-115) and nothing says so.
**Change:** delete `DEFAULT_BASE` (or rename `PROPOSAL_LIMIT` and drop the 512 constant), and add
to rules: "Limits are at least 1 character; 0 is rejected at validation."

## GF7 (Major) — "one larger reply" is unstated under no default limit
**Right and it is the same bug as GF1.** With no base limit, 1,024 after a skip is *restrictive*,
not "larger", so the wording is false. Whether 1,024 applies with no base, and what happens when
the base is above 1,024, are both unstated.
**Change:** reword rule[2] as "After a busy skip, the next discussion reply is limited to 1,024
characters (or the table limit if that is larger), once; then normal rules return." That single
sentence closes GF1, GF5's compare half and GF7.

## GF8 (Major) — active decisions still describe removed scheme + unit mix
**Right.** Same evidence as GF3. Unit mix: `truncate_to` counts `chars()` but cuts at grapheme
boundaries (rules.rs:23-37); the block check in `submit` counts `chars()` only (turn.rs:129).
**Change:** supersede the four decisions (GF3), and state the unit once: "Length is the number of
Unicode scalar values (Rust `char`); a character is never split because proposals are cut at a
grapheme boundary." No mixing in text.

## GF9 (Major) — how an agent learns its limit before being blocked
**Right, and it is the practical consequence of GF2.** With limits set, every agent that writes
long is silently failed with a notice that only arrives *after* the block, on its next turn.
**Change:** code (b) from GF2 — put the allowance line in the discussion prompt (and the review
prompt). This is the only way the agent can comply.

## GF10 (Major) — what a blocked message becomes
**Right.** The description never says it becomes `Outcome::Failed`, that it is not sent to JEV,
and that the author is told at its next turn via `seat.notices` (`prompts::too_long`,
turn.rs:131, delivered at turn.rs:52-55), while the bus gets a non-accepted `Contribution` with
`accepted:false, judged:false` and reason "over the limit" (turn.rs:132-144).
**Change:** add a rule: "A blocked reply is published as a rejected contribution, counted as a
failed turn, never sent to JEV; the seat is told the character counts on its next discussion
turn (not immediately)."

## GF11 (Nit) — who sets the limit
**Right.** It is `TableConfig::base_allowance` / `recovery_allowance` (config.rs:154-161), set at
table creation; the chair cannot change a running table's limit, and agents cannot.
**Change:** add rule: "The table's host sets both limits when the table is created; the chair
and agents cannot change them during a table." Replace "the owner's length experiment" with
"No limit by default (owner's 2026-11-07 experiment)."

## GF12 (Nit) — stale note, undefined terms, stale README references
**Right.** The investigation note says "the current spec truncates", which contradicts the block
rule. "bank", "session mode", "busy skip" are unexplained. README 4.x references describe the
old scheme.
**Change:** rewrite the investigation note as "Run 1 excluded five over-512 submissions; the
rule now blocks rather than cuts; the note is history only." Drop the "bank/session mode"
vocabulary from superseded entries by quoting the old terms in brackets. Remove or re-scope the
README 4.x entries to the new rules, or mark them superseded.

## Net: which are code fixes

- Code: `limit_for` (GF1, GF5 compare, GF7); recovery consumption in review/tool paths (GF5);
  allowance line in prompts (GF2, GF9); delete `DEFAULT_BASE` (GF6).
- Description only: GF3, GF4, GF8, GF10, GF11, GF12.
- GF4 proposal cutting is a description fix unless the `topic poll` element changes too.
