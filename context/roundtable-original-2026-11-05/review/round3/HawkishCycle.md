# HawkishCycle — Round 3 independent verification

Authority order: owner decisions in `docs/TRACEABILITY.md` L/M/N, then `README.md`,
then `Roundtable_ACP_Integration_Design.md`. Code comments and builder notes are not
authority. I changed no file outside `review/round3/`.

Scope. `VERDICTS.md` (the reconciled table) left **F06–F08** to me and **F13–F16** to
AlloyedReaper. AlloyedReaper's first file (read at 22:22) recorded only a kickoff proposal
and "Verification pending"; I therefore verified **F06, F07, F08, F13, F14, F15, F16**
myself to leave nothing uncovered. AlloyedReaper later did substantial work on F12–F18
(second file, 22:25) with custom probes under `review/round3/`, and found a real defect
(N01, below). I adopt and re-verified N01 against the current source. I also independently
cross-checked F01, F04 and F19 where other reviewers flagged gaps.

**The source changed live during this review** (AlloyedReaper notes an F14 edit at 22:23;
the crate's test suite gained `a_seat_with_tools_is_told_about_them`). I re-read the
current `turn.rs`/`engine.rs`/tests and re-ran everything at the end:
`cargo test -p roundtable --test engine` → 16 passed; `--test rules` → 6 passed;
`--test config` → 3 passed; `cargo test --workspace --no-fail-fast` → all green on the
final clean run; `cd adapters/openrouter-acp && npm test` → 25 passed. Verdicts below are
against the current source.

## F06 — Stale proposals enter scoring or later polls — FIXED

Fix, all four required properties present in `crates/roundtable/src/turn.rs` and `engine.rs`:
1. **Bind activity to a poll ID.** `Polling` (`engine.rs:113-118`) carries `asked` (seats
   asked in *this* poll) and `scoring: Option<u64>` (frozen once proposals go to JEV).
   `offer` sets `Activity::Proposing(prompt)` (`engine.rs:538`); `on_completed` gates on
   `activity.prompt() == Some(event.prompt)` (`engine.rs:602`), so a reply to an old
   poll's prompt never reaches a later poll's handler.
2. **Require current waiting membership.** `on_proposal` (`turn.rs:226-231`) rejects a
   reply when `polling` is None, when `!p.asked.contains(&i)` ("after the poll it answered
   had ended"), or when `p.scoring.is_some()` ("after the proposals went to JEV").
3. **Reject additions after scoring begins.** A Proposing seat that starts a tool is removed
   from `waiting` (`on_tool`, `engine.rs:590-594`), letting `finish_polling` start scoring;
   its late reply then hits the `p.scoring.is_some()` rejection.
4. **Select from the exact immutable vector judged.** `finish_polling` (`turn.rs:253-285`)
   sorts proposals by seat, snapshots the Vec, and builds `pN_M` keys from those indices;
   `complete_polling` (`turn.rs:304-311`) rebuilds the same Vec from the same
   `polling.proposals` and scores with the same keys. No mutation is possible after
   `scoring` is set.

Test: `crates/roundtable/tests/engine.rs:348`
`a_late_proposal_does_not_enter_a_decided_poll` — Cy starts a tool while proposing
(`FAKE_TOPIC_DELAY_MS=3000`), the others decide several polls, and Cy's late proposal is
reported "not counted" and never scored or proposed. Ran it: passes. Covers arrival during
scoring and during later polls. **FIXED.**

## F07 — Topics change after judging is disabled — FIXED

Fix: `settings_changed` (`engine.rs:811-827`), invoked by both `SetJudging`
(`engine.rs:769-772`) and `SetJevKey` (`engine.rs:773-776`), drops in-progress work when
`!topics_active()`: `polling.take()` (collecting *or* scoring), `advance.take()`,
`topic_due = false`, `rounds.reset()`, `round_left = seats.len()`. Recheck at commit:
`step()` applies a queued advance only via `.filter(|_| self.topics_active())`
(`engine.rs:454`); `on_scored` (`turn.rs:288-291`) ignores a result whose `scoring`
ticket no longer matches (the dropped poll), so an in-flight JEV reply cannot commit a
topic. Owner M ("topics require JEV") is respected.

Test: `crates/roundtable/tests/engine.rs:371`
`turning_judging_off_mid_poll_stops_topic_selection` — SetJudging(false) during a poll
produces the "Topic selection stopped" notice and no `roundtable.topic` event. Ran it:
passes. The finding also asked for scoring-phase and queued-advance setting changes; the
collection-phase regression is tested, the other two are covered by the code paths above
but have no dedicated test — a coverage note, not an unrepaired failure. **FIXED.**

## F08 — Corrupt identity history is silently replaced — FIXED

Fix: `update_profile` (`crates/roundtable-web/src/app.rs:415-434`):
- Initialize fresh **only on `ErrorKind::NotFound`** (`:424`); other read errors are
  returned (`:425`) and parse errors become `InvalidData` (`:423`).
- Schema check rejects a non-object / bad shape (`:427-429`) instead of overwriting.
- Atomic write to sibling `.<name>.json.tmp` then `rename` (`:431-433`).
- Writers are serialized: the only production callers are `save_rating` / `save_feedback`
  from the single recorder task in `AppState::new` (`app.rs:72-96`); errors are surfaced
  loudly via `loud` (`:77-82`) as an error `Notice` plus `eprintln!`. Verified by grep:
  no other caller writes profiles.

Test: `crates/roundtable-web/src/app.rs:591`
`identity_profiles_are_never_silently_replaced` — accumulates 160 points over two saves,
asserts no temp file remains, writes `"{ truncated"`, asserts `update_profile` returns
`InvalidData` and the corrupt file is untouched verbatim, and checks feedback/path-traversal
rejection. Ran it: passes. **FIXED.**

## F13 — Review requests omit their enforced allowance — FIXED

`ask_to_review` (`engine.rs:521-528`) builds `REVIEW + "\n\n" + allowance(current)`; the
review instruction precedes the owner's final current-allowance line. `REVIEW`
(`prompts.rs:69`) no longer replaces the allowance. `allowance()` uses
`seat.allowance.current` (dynamic, includes credits).

Test: `crates/roundtable/tests/engine.rs:163` `a_lone_free_agent_is_asked_to_review_once_while_the_other_works`,
assertion `:184-186` checks the review prompt ends with "Characters to Respond" (ran, passes).
The finding's requested **nondefault-bank review test** is provided by AlloyedReaper's probe
`review/round3/alloyed-engine-probe.rs` (base 1537, exact "You have 1537 Characters to
Respond" assertion; `alloyed-nondefault-test.log` PASS). So the gap is closed. **FIXED.**

## F14 — Missing peer ratings and empty proposals pass silently — PARTIAL

`on_proposal` (`turn.rs:245-249`) reports `Reply::Empty` as a `TurnFailed` event plus an
error notice. `on_rating` (`turn.rs:361-399`) computes `unrated` = every peer minus those
named in the card; `{}` (all missing), partial sets (some missing), and unparseable replies
produce an explicit error `Notice` (`:390`, `:396-398`). No unlimited retry is added
(`:394-395`). Test `crates/roundtable/tests/engine.rs:425` `missing_peer_ratings_are_reported`
(empty `{}` → "did not rate … those ratings are missing") passes.

**But the fix has a concrete hole (N01, below): a `null` or non-object peer card is removed
from `unrated` before its shape is checked, so a required peer rating is silently dropped
with no notice — exactly the silent-omission failure F14 was meant to remove.** Empty
proposals and partial peer sets also still lack dedicated runtime assertions. Because one
required "report missing peer ratings" case is not repaired, F14 is **PARTIAL**, not FIXED.

## F15 — Immediate after-work acceptance omits productivity accounting — FIXED

`resolve_reply` (`turn.rs:69-95`) records productivity on **both** paths exactly once:
- Immediate (judging off / no key): `submit` returns `Outcome::Accepted`; `:91-93`
  `if after_work && outcome == Accepted { self.rounds.record_accept() }`.
- Async judged: `:85-88` returns early for a floor `Contributed`; `on_judged`
  (`turn.rs:145-151`) calls `rounds.record_accept()` on acceptance via `count`.
For `after_work=true` the immediate path records and returns `None` (no double count); the
judged path records once through `on_judged`. No path records twice.

Tests: `crates/roundtable/tests/engine.rs:129` `tool_activity_marks_an_agent_working_and_the_table_moves_on`
drives immediate acceptance and asserts `after_work == true` (ran, passes). The finding's
exact "nonproductive round + immediate worker acceptance + settings toggle" scenario is
proven by AlloyedReaper's probe `review/round3/probe/src/bin/f15c.rs` →
`alloyed-f15-toggle.log`: "round topic_may_advance: Some(false) (must be false: acceptance
recorded → productive)" and the full scenario PASS. So the verification gap is closed.
**FIXED.**

## F16 — Chair allowance display ignores configured base — FIXED

`roundtable.opened` carries `base_allowance` (`engine.rs:373`). UI stores it:
`index.html:214` sets `t.base = d.base_allowance` and back-fills existing seats; new seats
use `allowance: t.base` (`:207`); accepted-message resets use `t.base` (`:229`). `t.base`
defaults to 512 (`:173`) but `opened` is the first event for every table, so a configured
base (e.g. 1024) is in effect before any seat/reset is displayed.

Tests: `crates/roundtable/tests/engine.rs:407` `the_first_turn_carries_the_owners_prompt_with_placeholders_filled`
(base 700 → "You have 700 Characters to Respond"; ran, passes). The JS display is proven by
AlloyedReaper's `review/round3/alloyed-ui-probe.mjs` (`alloyed-ui-probe.log` PASS): base
1024 initialization, bank 3072 surviving a veto, acceptance resetting to 1024 — the
finding's exact base/veto/reset cases. **FIXED.**

## Cross-checks that change the shared VERDICTS

- **F04 — remove the "test gap" caveat.** NobleChaos marked `FIXED (test gap)` claiming
  no exited-leader cancellation test was found. The tests exist (AlloyedReaper concurs):
  `adapters/openrouter-acp/test/adapter.test.ts:587-651` `stopAfterLeaderExit`, used by
  `:655` (cancel) and `:659` (disconnect). `npm test`: 25/25 pass including both. With
  `tools.ts:277-286` (unconditional `process.kill(-pid, SIGKILL)`, ESRCH swallowed) this
  is **FIXED with test proof**.
- **F12 — remove the "test gap" caveat.** The live source gained
  `crates/roundtable/tests/engine.rs:443` `a_seat_with_tools_is_told_about_them`, which
  asserts `seat.ready.tools == true` and that the prompt contains "- Tools: `advance`".
  Combined with the no-tools assertion in `the_first_turn_...` (`:407`), F12 now has positive
  and negative automated coverage. Ran it: passes. F12 = FIXED, no gap.
- **F01 — concur FIXED.** `SECRET_ENV` (config.rs:28) includes ROUNDTABLE_TOKEN, scrubbed
  from every seat (`:36-41`); test `tests/config.rs:15`. The adapter's `WITHHELD_ENV`
  (`tools.ts:34`) need not list the token because the token never reaches the harness
  process, hence cannot reach model-executed subprocesses.
- **F19 — concur FIXED, and the reorder is necessary.** I confirmed Rust `Command` env
  semantics are call-order dependent: `.env_remove("K").env("K","shared")` → "shared";
  `.env("K","shared").env_remove("K")` → "unset". So the F19 bug was real and
  `process.rs:65-70` (remove before `.envs`) is the correct fix; test
  `explicit_env_wins_over_removal` (`:198`) spawns a real child and passes.

## New defects / regressions introduced by the fixes

**N01 (P2) — a null/non-object peer card bypasses the F14 missing-rating reporting.**
Found by AlloyedReaper; re-verified against current source here.
- **Location:** `crates/roundtable/src/turn.rs:369-371` (the new F14 `on_rating` loop).
- **Scenario:** table ends with two live participants; Ada replies
  `{"BoGenesisName": null}`. The loop runs `unrated.retain(|n| n != to_name)` (`:370`)
  **before** `let Some(ratings) = card.as_object() else { continue }` (`:371`). `null` (or a
  number/string) fails `as_object`, so `continue` fires: no `RatingGiven` is published, the
  peer is already gone from `unrated`, and the final "did not rate … those ratings are
  missing" notice (`:396-398`) is not emitted. A required peer rating is silently lost and
  `rating_done` (`:399`) lets End proceed — the exact silent-omission F14 targeted. This is
  about *presence* of a peer rating, not category-value validation struck by L#12.
- **Fix:** remove a peer from `unrated` only after its uniquely resolved **object** card is
  actually recorded (immediately after publishing `RatingGiven`); keep malformed/unknown
  peers in `unrated` so the existing notice fires. Add tests for null/non-object cards,
  `{}` and partial peer sets; no retries, no category-value validation.
- **Proof:** AlloyedReaper's `review/round3/alloyed-engine-probe.rs`
  `null_peer_rating_is_silently_discarded` (`alloyed-null-rating-recheck.log`: PASS) pins
  Bo's genesis session, has Ada return `{"BoGenesisName": null}`, and observes the table
  ends with only Bo's rating and no missing-peer error (documents the defect). The plain
  `{}` test `missing_peer_ratings_are_reported` still passes — the hole is specific to
  malformed cards.

My own new-defect hunt in F06–F08/F13–F16 found no other introduced regression (I traced
each changed path for double-counts, silent drops and invented timers). Two **pre-existing
verification-reliability observations** (not introduced by round-3 fixes), reported because
they can mask regressions:
1. `crates/acp-host/tests/harness.rs:314` `shutdown_ends_the_whole_process_group` and
   `:279` `an_exit_mid_turn_fails_the_prompt_once_before_the_exit_event` are flaky under
   parallel load (~1/6 harness-suite runs; I observed the grandchild "survived shutdown"
   once on the first workspace run and an exit-ordering failure once). Root:
   `process.rs:107-111` `killpg(SIGKILL)` does not wait for the group to be reaped before
   `HarnessExited`. Both pass in isolation (8/8) and on a clean workspace run (final run:
   12/12 harness tests green). Fix (not applied): poll `/proc/<pid>/stat` until `Z`/gone
   with a bounded loop, or `waitpid` the group — test/observability hardening, not an
   invented product timer.
2. F19's fix depends on `spawn()` keeping `.env_remove()` before `.envs()` call order
   (`process.rs:65-70`); a future reorder would silently re-leak the opted-in key. Add a
   guarding comment/assertion. Maintainability fragility, not a current failure.

## Split reconciliation (final)

Kickoff (AlloyedReaper) proposed F01–F04 / F05–F08 / F09–F12 / F13–F16 / F17–F19 but
marked "awaiting acceptance". Participants self-organized: BalmyBoron F01/F02/F12/F17/F18
(+F19), BrinySteel F03/F05/F09/F10/F11, NobleChaos F03/F04/F05/F19. VERDICTS.md then left
F06–F08 to HawkishCycle and F13–F16 to AlloyedReaper. AlloyedReaper subsequently accepted
"F12–F18" and produced real verification incl. the N01 defect and probes that close the
F13/F15/F16 coverage gaps. I verified F06–F08 and F13–F16 independently. Net: every item
has ≥1 checker (most ≥2); F14 is the only non-FIXED item (PARTIAL, via N01).
