# Round 3 verdicts — F01–F19

Each F-item: verdict, checker(s), and key evidence. Authority order: TRACEABILITY L/M/N, README, ACP design. Code comments/builder notes are not authority. No file changed outside `review/round3/`. Verdicts are against the current source (live changes noted: an F14 edit ~22:23 and a new F12 test; final `cargo test --workspace --no-fail-fast` all green, `npm test` 25/25).

| Item | Verdict | Checked by | Evidence |
|---|---|---|---|
| F01 | FIXED | BalmyBoron, HawkishCycle | config.rs:28 SECRET_ENV (ROUNDTABLE_TOKEN) + env_remove; test config.rs:15; token never reaches harness, so model subprocesses safe |
| F02 | FIXED | BalmyBoron | permission.rs resolve() dangling links; test :188; tools.ts resolveReal + test adapter.test.ts:406 |
| F03 | FIXED | BrinySteel, NobleChaos | engine.rs settle_rating on all prompt-ending paths (:628, called :622/:665/:695); test engine.rs:320 (fail+crash) |
| F04 | FIXED | NobleChaos, HawkishCycle, AlloyedReaper | tools.ts:277-286 unconditional group kill, ESRCH swallowed, settle on close. TESTS EXIST (gap withdrawn): adapter.test.ts:587-651 stopAfterLeaderExit, :655 cancel, :659 disconnect; `npm test` 25/25 pass incl. both |
| F05 | FIXED | BrinySteel, NobleChaos | tables.rs catalog() shared resolver + LaunchSpec node+argv; test tables.rs:150 |
| F06 | FIXED | HawkishCycle | turn.rs on_proposal:226-231 asked/scoring membership + immutable judged vector (finish_polling:253/complete_polling:304); engine.rs:602 prompt gate, :590-594 on_tool; test engine.rs:348 (passes) |
| F07 | FIXED | HawkishCycle | engine.rs:811-827 settings_changed drops polling/advance/topic_due; :454 advance filter topics_active(); turn.rs:288 on_scored ticket guard; test engine.rs:371 (passes). Scoring-phase/queued-advance cases covered by code, no dedicated test |
| F08 | FIXED | HawkishCycle | app.rs:415-434 update_profile (NotFound-only init, InvalidData on parse/shape, sibling-tmp+rename, single-writer task); test app.rs:591 (passes) |
| F09 | FIXED | BrinySteel + BalmyBoron | record.rs harness_id object form; engine.rs:423-429 MonitorUnavailable notice; index.html harnessId/tableOf/seatOf; test record.rs:65 |
| F10 | FIXED | BrinySteel + BalmyBoron | no keepalive (app.rs:346); event-driven loadPast on ended (index.html:247); no timers remain |
| F11 | FIXED | BrinySteel + BalmyBoron | save_feedback persists to identity; loud errors; truthful tool replies; test app.rs:607 |
| F12 | FIXED | BalmyBoron, AlloyedReaper | prompts.rs process(tools) + turn.rs:39 seat.tools; engine.rs:865 offered; test engine.rs:406 no Tools line AND new test engine.rs:443 a_seat_with_tools_is_told_about_them (positive). Gap closed; both pass |
| F13 | FIXED | HawkishCycle, AlloyedReaper | engine.rs:521-528 review+allowance(current); prompts.rs:69 REVIEW; test engine.rs:163 (:184-186). Nondefault-bank (1537) proven by alloyed-engine-probe.rs / alloyed-nondefault-test.log PASS |
| F14 | PARTIAL | HawkishCycle, AlloyedReaper | turn.rs:245-249 empty-proposal report; :361-399 on_rating missing-peer notices; `{}` test engine.rs:425 passes. BUT N01 (below): a null/non-object peer card is dropped from `unrated` before its shape is checked (:370-371), so a required peer rating is silently lost with no notice. Empty proposals/partial sets lack dedicated runtime tests. Concrete failure scenario → PARTIAL |
| F15 | FIXED | HawkishCycle, AlloyedReaper | turn.rs:91-93 immediate accept record_accept + :145-151 on_judged async; exactly-once; test engine.rs:129. Required toggle scenario proven by probe/src/bin/f15c.rs → alloyed-f15-toggle.log PASS (topic_may_advance=false) |
| F16 | FIXED | HawkishCycle, AlloyedReaper | index.html:214 t.base from opened base_allowance; :207 new seat, :229 accepted reset; engine.rs:373; test engine.rs:407 base 700. JS display proven by alloyed-ui-probe.mjs / alloyed-ui-probe.log PASS (base 1024, veto 3072, reset 1024) |
| F17 | FIXED | BalmyBoron, AlloyedReaper | prompts.rs:64-65 no "privately"; rules.rs:12 PROPOSAL_LIMIT 512 kept; literal/absence checked |
| F18 | FIXED | BalmyBoron, AlloyedReaper | turn.rs:32-35 filters Failed/Gone; test engine.rs:390 a_failed_seat_is_not_listed_as_joining |
| F19 | FIXED | BalmyBoron, NobleChaos, HawkishCycle | process.rs:65-70 env_remove before envs (call-order dependent, confirmed); config.rs inserts key; test explicit_env_wins_over_removal (passes). Reorder-fragility note |

**Result: 18 FIXED, 1 PARTIAL (F14, via N01).** No NOT FIXED / unrepaired item among F01–F13, F15–F19. Earlier "test gap" caveats on F04 and F12 were withdrawn (tests found and run). F07/F14 carry coverage notes for specific requested cases covered by code but lacking a dedicated test; F15's and F16's gaps were closed by AlloyedReaper's probes. F13's nondefault-bank gap closed by probe.

## New defects / regressions introduced by the fixes

**N01 (P2) — null/non-object peer cards bypass F14 completeness reporting.** Found by AlloyedReaper, re-verified by HawkishCycle.
- Location: `crates/roundtable/src/turn.rs:369-371` (the F14 `on_rating` loop).
- Scenario: Ada replies `{"BoGenesisName": null}`. `unrated.retain(|n| n != to_name)` runs at :370 *before* `card.as_object()` at :371; a null/number/string card fails `as_object`, so `continue` fires — no `RatingGiven`, the peer is already gone from `unrated`, and the "did not rate … missing" notice (:396-398) never fires. A required peer rating is silently lost. Presence, not category-value validation (L#12).
- Fix: remove a peer from `unrated` only after its uniquely resolved object card is recorded (right after publishing `RatingGiven`); keep malformed/unknown peers so the notice fires. Add null/non-object, `{}`, partial-set tests; no retries.
- Proof: `review/round3/alloyed-engine-probe.rs` `null_peer_rating_is_silently_discarded` (alloyed-null-rating-recheck.log PASS) documents the silent drop; the plain `{}` test still passes.

Two **pre-existing verification-reliability observations** (not introduced by round-3 fixes), in HawkishCycle.md:
- `crates/acp-host/tests/harness.rs:314` `shutdown_ends_the_whole_process_group` and `:279` `an_exit_mid_turn_fails_the_prompt_once_before_the_exit_event` flaky under parallel load (~1/6 runs); root `process.rs:107-111` `killpg(SIGKILL)` not waiting for group reap before `HarnessExited`. Pass in isolation (8/8) and on the final clean workspace run. Can mask regressions. Fix: bounded `/proc/<pid>/stat` poll to `Z`/gone, or `waitpid` the group.
- F19 relies on `spawn()` `.env_remove()` before `.envs()` call order (`process.rs:65-70`); a reorder would re-leak the opted-in key. Add a guarding comment/assertion.

## Split reconciliation (final)

Kickoff (AlloyedReaper) proposed F01–F04 / F05–F08 / F09–F12 / F13–F16 / F17–F19, "awaiting acceptance", no verification. Participants self-organized: BalmyBoron F01/F02/F12/F17/F18(+F19), BrinySteel F03/F05/F09/F10/F11, NobleChaos F03/F04/F05/F19; VERDICTS left F06–F08 to HawkishCycle and F13–F16 to AlloyedReaper. AlloyedReaper later accepted "F12–F18" and produced real verification incl. N01 and probes closing F13/F15/F16 gaps. HawkishCycle verified F06–F08 and F13–F16 independently. Every item now has ≥1 checker (most ≥2). Per-item detail in each participant's `.md`; AlloyedReaper's probe artifacts/logs live under `review/round3/`.
