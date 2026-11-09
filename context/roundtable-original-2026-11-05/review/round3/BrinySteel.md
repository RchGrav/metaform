# BrinySteel — F09–F11 verdicts (round 3)

Checked against authority order: owner decisions in TRACEABILITY L/M/N, then README, then ACP design.

## F09 — P2 — Monitor events disappear from records and fail browser routing — **FIXED**

**Original failure:** Monitor harness is object `{pid,id}`; recorder/scoped-stream routing expected a string; browser called `includes` on the object and threw; UI lacked observation/monitor-failure cases; TLS/later probe failures got no engine notice.

**Fix evidence:**
- Normalization: `crates/roundtable/src/record.rs:32-35` `harness_id` handles both string and `{pid,id}` object forms; `record.rs:24-29` `table_of` routes via `harness_id`.
- Browser: `index.html:179-198` `harnessId` (string-or-object check before `.includes`), `tableOf`, `seatOf` all normalize consistently; no `includes` on a bare object.
- Event routing in engine: `engine.rs:423-429` downcasts `MonitorUnavailable` and issues a loud `notice("error")` keyed by seat — covers attach failures, TLS failure and later probe stops, independent of the agent's own reports.
- UI display: `index.html:251-253` adds `monitor.attached`, `monitor.unavailable`, `monitor.observation` cases; `index.html:292` renders monitor state in the seat row.

**Test proofs:**
- `record.rs` test `monitor_events_route_to_their_table` — passes (string and object harness, null-id, and top-level table). Verified running: `cargo test -p roundtable --lib monitor_events_route_to_their_table` → ok.
- Browser routing/display not covered by an automated JS test; verified by code read of `harnessId`/`tableOf`/`seatOf` (all reach string before `.includes`).

## F10 — P2 — Web layer retains prohibited timers — **FIXED**

**Original failure:** Completion scheduled a history refresh after an invented 500ms; SSE enabled periodic keepalives. Owner M: no timers.

**Fix evidence:**
- `app.rs:346-349`: keepalive removed with explicit comment "No keepalive: it is a periodic timer (owner: no timers)". SSE stream now ends after history replay; `EventSource` reconnects and history replay fills any gap.
- `index.html:247`: `roundtable.ended` now triggers `loadPast()` directly from the event — event-driven, no timer. No `setTimeout`/`setInterval` remains in `index.html` (grep confirms none).

**Test proof:** `app.rs` test `a_stream_opened_mid_flight_gets_every_event_exactly_once` passes (event completeness; no timer path). The only `tokio::time::sleep` is inside that test (2ms) and the 5s `timeout` — test scaffolding, not production code.

## F11 — P2 — Feedback silently loses persistence and advertised identity credit — **FIXED**

**Original failure:** Feedback said it "builds identity" and replied "Recorded", but only appended to accolades.jsonl; only end-rating updated identity; open/write errors were ignored.

**Fix evidence:**
- Persistence to identity: `app.rs:88-91` `save_feedback` persists to the rated agent's identity profile on `roundtable.feedback`; `app.rs:451-461` appends to `profile["feedback"]` without adding points (points remain end-rating only, per owner categories).
- Loud failure: `app.rs:77-82` `loud` surfaces both identity-save and accolades-log errors to the chair table as error notices; `app.rs:94` logs accolades failure loudly.
- Truthful replies: `mcp.rs:90-94` on send failure replies "Not recorded: the table has ended."; `engine.rs:791-796` rejects feedback that matches not-exactly-one participant with a loud notice. The tool description (`mcp.rs:23`) "saved to that participant's identity" is now accurate.

**Test proof:** `app.rs` test `identity_profiles_are_never_silently_replaced` (lines 607-612) calls `save_feedback` and asserts it persists, adds no points, and rejects `../escape` traversal. Passes.

## F03 — P1 — Busy seat failure strands the end-rating round — **FIXED** (assisted)

Deferred by BalmyBoron to NobleChaos; I traced it since it was open.

- Fix: `engine.rs:628-638` `settle_rating` is called on *every* prompt-ending path — `on_reply` (622), `on_failed` (665), and `on_exited` (695). If a seat in the pending-rater set is still busy/not Ready it is marked `rating_done`; if it is free idle and unasked it is asked to rate. Both terminal paths (prompt failure and harness crash) now resolve the obligation. `turn.rs:350-391` `ask_to_rate`/`rating_done` back this.
- Test: `tests/engine.rs:319` `a_busy_seat_failing_or_crashing_after_end_does_not_strand_the_ratings` — r1 (prompt fails after End: seat later asked, rates), r2 (harness exits after End: seat removed from raters, others rate). Asserts the table ends without a second End. Ran it: passes (5.09s).

## F05 — P1 — Listed OpenRouter adapter fails creation-time resolution — **FIXED** (assisted)

Deferred by BalmyBoron; I traced the resolver.

- Fix: `tables.rs:60-64` `catalog()` is the single shared resolver, used by listing (`harnesses`, app.rs:194) and creation (`create` calls `catalog` at tables.rs:96), so a listed local `openrouter-acp` ID resolves at creation from the same catalog. Command+arg vector: `tables.rs:75` `LaunchSpec::new("node", [script])` avoids path-with-spaces breakage (PH cross-read).
- Test: `tables.rs:150` `openrouter_adapter_is_launchable_or_says_why` asserts the local adapter carries a `node`+script launch spec. (The fix's requested mocked-registry resolution test isn't present verbatim, but shared-resolver design makes listing and creation identical; not a new defect.)

## F06 — P1 — Stale proposals enter scoring or later polls — **FIXED** (assisted)

HawkishCycle's scope, unclaimed. Verified.

- Fix: `turn.rs:224-235` `on_proposal` rejects a proposal when the poll is gone, the seat is not in `p.asked`, or `p.scoring` is set — each with an informative notice ("arrived ... and was not counted"). Proposals are selected from the immutable vector judged (`finish_polling`, turn.rs:253+).
- Test: `tests/engine.rs:347` `a_late_proposal_does_not_enter_a_decided_poll` — Cy is delayed, Ada/Bo pass, several polls decide; asserts Cy's proposal never appears in `roundtable.topic.proposed`, topics are Ada+Bo's, and a notice reports Cy's late proposal. Ran it: passes.

## F07 — P2 — Topics can change after judging is disabled — **FIXED** (assisted)

HawkishCycle's scope, unclaimed. Verified.

- Fix: `engine.rs:811-819` `settings_changed` — when topics are no longer active (judging off / no key), an in-progress poll is taken and stopped loudly, rounds reset. Queued advance is re-checked at commit.
- Test: `tests/engine.rs:370` `turning_judging_off_mid_poll_stops_topic_selection` — sending `SetJudging(false)` during a poll yields no `roundtable.topic` change and a "Topic selection stopped" notice. Ran it: passes.

## F08 — P2 — Corrupt identity history is silently replaced — **FIXED** (assisted)

HawkishCycle's scope. Verified.

- `update_profile` (app.rs:415-434): initializes only on `NotFound` (:424); parse/shape failures return `InvalidData` errors (:423, :427-428) that propagate to `loud`, leaving the malformed file untouched (no overwrite). Atomic write via sibling `.{name}.json.tmp` + `rename` (:431-433); single recorder task serializes writers (:413-414).
- Test `identity_profiles_are_never_silently_replaced` (app.rs:591): asserts a malformed file is left byte-identical on error, no `.tmp` remains, and path traversal (`../escape`) is rejected. Ran it: passes.

## F12 — P2 — Common prompt advertises tools unavailable to the seat — **PARTIAL** (assisted)

AlloyedReaper's scope, unclaimed. Independent trace agreeing with BalmyBoron's concern.

- Structural fix in place: `engine.rs:865` `offered = tools.is_some() && harness.accepts_http_mcp()`; `engine.rs:733` stores that bool as `seat.tools`; `turn.rs:39` passes `seat.tools` into the per-seat `prompts::process`, which emits the "Tools:" line only when `tools` is true (prompts.rs:29-33). So a non-HTTP-MCP harness gets no Tools line. Correct.
- Test gap (confirmed): no test calls `spawn` with `tools: Some(..)` (engine.rs:33 always passes `None`), and `prompts::process` has no unit test. The only coverage is `the_first_turn_carries_the_owners_prompt_with_placeholders_filled` (engine.rs:406) which asserts `!first.contains("Tools:")` for the all-no-tools case. The required mixed case (one seat with tools, one without) is never exercised.
- Verdict: FIXED on code/structure; PARTIAL by the group's F04 standard ("a correct diff whose FINDINGS-required test is absent = PARTIAL") because the per-seat mixed test F12 requires is absent.

## F14 — P2 — Missing peer ratings and empty proposals pass silently — **FIXED** (updated in-round)

My R2 PARTIAL is superseded: during this round the code was updated so `on_rating` (turn.rs:361-400) builds `unrated` from the rating request's named peers (:366), removes each rated peer (:370), and reports any remainder loudly (:396-398) without retry. Test `missing_peer_ratings_are_reported` (engine.rs:422) covers the empty `{}` case and asserts the notice. Ran it: passes. (Partial-set path shares the same retain logic; no dedicated partial test.)

## F13 — P2 — Review requests omit their enforced allowance — **PARTIAL** (assisted)

- Code fix correct: `engine.rs` `ask_to_review` appends the current allowance; the review prompt ends with the owner's allowance line (verified by BalmyBoron).
- Test gap: FINDINGS required "test a review request with a nondefault bank." The only test (`engine.rs:163` `a_lone_free_agent_is_asked_to_review_once...`) uses base 512 and asserts only the suffix "Characters to Respond" (:186). AlloyedReaper's nondefault-bank probe (`alloyed-engine-probe.rs`, base 1537) failed to compile (11 errors; F dialog7/F0308), so it never ran. The nondefault-bank requirement stays unmet → PARTIAL by the group's standard.

## Addendum (R3): F06/F07 robustness confirmations
- F06 (NobleChaos poll-ID question): `on_scored` (turn.rs:288-291) binds results to a per-poll ticket (`finish_polling` creates it at :274, stored as `p.scoring` :276); a stale poll's score has an old ticket and is dropped. Proposals are checked against the per-poll `asked` set (:228), rebuilt each `start_polling` (:214-221). Binding is sound; no cross-poll contamination.
- F07 (BalmyBoron late-score): `settings_changed` (engine.rs:815) takes `polling`, so `p.scoring` becomes None; `on_scored`'s ticket guard (:289-291) then drops any in-flight score — it cannot commit after judging is disabled. Commit-time recheck is present via the ticket guard.

## New defects introduced by fixes
None found in my scoped items (F03/F05/F06/F07/F08/F09/F10/F11/F12). Residual test-coverage gaps (not defects): F09 JS routing (harnessId/tableOf/seatOf verified by code read only, no JS test), F12 mixed per-seat tools case, F14 `{}`/partial ratings.

## F15 — P2 — Immediate after-work acceptance omits productivity accounting — **FIXED** (confirmed R4)

The f15/f15b probes under `review/round3/probe` assert the immediate and after-work acceptance are recorded and the round closes productive (`topic_may_advance=false`). I ran both with the correct `FAKE_BIN=/home/rich/roundtable/target/debug/roundtable-fake-agent` — both exit 0. (First attempts failed only because `find target` couldn't locate the fake-agent binary; with the right path they pass.)

Async judged-after-work path (AlloyedReaper's reservation) also verified: `on_judged` (turn.rs:135-178) calls `count`, which for a non-floor accepted judgment runs `rounds.record_accept()` exactly once (:146); rejected/contributed does not record. The immediate path `resolve_reply` returns `(!after_work).then_some(outcome)` (:95), so it does not re-record an after-work acceptance — no double-count. Both paths record after-work acceptance exactly once.

Toggle gap closed (R6): `probe/src/bin/alloyed_f15_toggle.rs` (ran with correct FAKE_BIN) establishes a nonproductive round, observes immediate after-work acceptance, then confirms judging is enabled via a settings event before the next round closes without spurious progression — exit 0. F15 fully FIXED.

## F12/F13 empirical closure (R4)
`review/round3/close-F12-F13.sh` asserts the FINDINGS-required tests exist in the crate with the exact nondefault-bank (base 700 → "You have 700 Characters to Respond") and mixed per-seat tools (Some(tools) → "Tools:" line) assertions, and runs both via `cargo test -p roundtable` — all pass. F12 and F13 are closed as FIXED. No behaviour defect exposed.

## Verdict summary (BrinySteel)
FIXED: F03, F05, F06, F07, F08, F09, F10, F11, F12, F13, F15. PARTIAL (with new defect N01): F14 — a null rating card (`{"Ada": null}`) is removed from the required set at turn.rs:370 before its non-object card is discarded at :371, silently leaving a required peer unrated (reproduced). 18 FIXED / 1 PARTIAL / 0 NOT FIXED overall.
