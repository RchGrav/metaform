# AlloyedReaper — round 3 verification

Accepted revised split: F12–F18. Authority: TRACEABILITY L/M/N, then README, then ACP design; EXPECTATIONS read. I wrote only review/round3 files. Source changed externally during verification: turn.rs and engine tests gained an F14 fix at 22:23 local; the current-source assessment below supersedes my initial `{}` finding.

| Item | Verdict | Code and proof |
|---|---|---|
| F12 | FIXED | engine.rs:865 determines tool availability from endpoint presence and HTTP-MCP capability; :733 stores per-seat result; turn.rs:39 passes it to prompts.rs:29 conditional tools line. `the_first_turn_carries_the_owners_prompt_with_placeholders_filled`, tests/engine.rs:406, asserts no tools line for a seat without tools. Ran successfully: alloyed-first-test.log. Positive/mixed availability remains a coverage gap, not evidence of a failing fix. |
| F13 | FIXED | engine.rs:521–526 appends the **current** allowance after REVIEW. Strengthened existing lone-free-seat integration test under review/round3/alloyed-engine-probe.rs: base 1537, exact final `You have 1537 Characters to Respond` assertion. PASS in alloyed-nondefault-test.log. Original default-base test also passes (alloyed-review-test.log). |
| F14 | PARTIAL | Empty proposals now emit TurnFailed and error notice, turn.rs:245–249. Current on_rating computes missing peers (:366) and reports them (:396–397); current `{}` test `missing_peer_ratings_are_reported` passes (alloyed-empty-ratings-test.log). But :370 removes a peer before verifying its card is an object (:371), so a null peer card records nothing and produces no missing-peer error. See introduced defect N01. Partial peer sets and empty proposal runtime coverage still absent. |
| F15 | FIXED (gap closed by independent probe) | turn.rs:90–93 records immediate acceptance, async counterpart :145–150 records once. `probe/src/bin/alloyed_f15_toggle.rs` establishes an initial nonproductive round, observes immediate after-work acceptance, enables judging, verifies the judging-enabled settings event before the following RoundClosed, and asserts topic_may_advance=false. PASS: alloyed-f15-toggle.log. This addresses the original requested toggle scenario. |
| F16 | FIXED | index.html:214 stores base, :207 seeds seats with it, :228 resets only on acceptance. Executed **actual** table/routing/apply functions extracted from the HTML in alloyed-ui-probe.mjs; asserts base 1024 initialization, bank 3072 surviving veto, acceptance resetting to 1024. PASS: alloyed-ui-probe.log. |
| F17 | FIXED | prompts.rs:64–65 removes private label and retains PROPOSAL_LIMIT; rules.rs:12 retains 512. alloyed-ui-probe.mjs asserts literal absence and retained bound; PASS. |
| F18 | FIXED | turn.rs:32–35 excludes Failed/Gone, includes genuine Starting as joining. Existing integration `a_failed_seat_is_not_listed_as_joining`, tests/engine.rs:389, starts one broken and two live seats; checks failure event and no joining label. Ran successfully: alloyed-roster-test.log. |

## N01 — P2 — null peer cards bypass new completeness reporting

Location: crates/roundtable/src/turn.rs:370–371 (new F14 fix).

Scenario: table ends with two live participants; Ada returns `{"BoGenesisName": null}`. The peer is removed from `unrated`, its non-object card is discarded, no RatingGiven event is emitted, `unrated` is empty so no missing-rating notice is emitted, and rating_done (:399) allows End. This repeats the silent missing-rating failure through a newly added path. It concerns presence of a peer rating, not validation of category values struck by L#12.

Fix: remove a peer from `unrated` only once its uniquely resolved object card is actually recorded (immediately after publishing RatingGiven). Cover null/non-object cards, `{}`, and partial peer sets without retries or category-value validation.

Probe: alloyed-engine-probe.rs adds `null_peer_rating_is_silently_discarded`, pins Bo's genesis session, makes Ada return its name with null, and asserts the table ends with only Bo's rating and no missing-peer error. This test documents the defect rather than asserting desired behavior.

## Test execution limits

Tests use existing Rust build artifacts and a copied integration source linked with the same dependency fingerprints. All new binaries, logs and TMPDIR state are under review/round3. The first-prompt test's local fake JEV socket required escalation after sandbox denied bind; approved rerun passed. No paid services used. F13 compile initially failed due mismatched dependency artifacts; fingerprint-matched compilation succeeded, and the executable passed. Do not cite the earlier compile failure as current evidence.

Cross-check: F04 required tests **exist**, adapter.test.ts:655 and :659; stopAfterLeaderExit explicitly waits for leader ESRCH and exercises cancel plus abortAll. An earlier shared report's missing-test claim was stale.

## Final empirical follow-up

- Full existing engine binary: 16/16 passed, `alloyed-full-engine.log` (26.85s; loopback permissions approved).
- Full adapter suite against existing dist: 25/25 passed, `alloyed-full-adapter.log` (1.45s; approved rerun after sandbox child-runner failure). These passes do not cover the null-card hole.
- N01 reproduced again, `alloyed-null-rating-recheck.log`, 0.25s. Current source still removes the peer before discarding its null card; after unrelated edits the location is now turn.rs:367–368 (previously :370–371).
- F15 **FIXED**: stronger standalone probe now proves the actual settings-toggle scenario, as described in its row above. The earlier f15b probe's false topic_may_advance with judging off alone was insufficient: engine.rs opportunity always ANDs that field with topics_active. The new probe explicitly observes judging enabled before round closure.
- Current supported tally: **18 FIXED, 1 PARTIAL (F14), 0 NOT FIXED; one reproduced new defect N01.** Other participants' stale descriptions that this report contains only kickoff notes are superseded by this report and its saved test logs.
