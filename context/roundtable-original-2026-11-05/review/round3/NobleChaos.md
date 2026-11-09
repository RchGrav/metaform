# NobleChaos — Round 3 independent verification

Scope claimed: F03, F04, F05, F19 (independent cross-check; BalmyBoron also verifying F01/F03/F19/F05 per R2-2).
Authority: TRACEABILITY L/M/N > README > ACP design. Code comments/builder notes not authority.

## F03 — Busy seat failure strands the end-rating round — FIXED

Fix: `crates/roundtable/src/engine.rs:628-638` `settle_rating(i)` — called on all three terminal paths (`on_completed` :622, `on_failed` :665, `on_exited` :695). If the seat still owes ratings (`left.contains(&i)`) and is not `Ready`, it is removed via `rating_done(i)`; if Ready+Idle and not yet asked, `ask_to_rate(i)`. This covers Working/Reviewing/Floor/Proposing busy seats (all become Idle before `settle_rating` is called in each handler) — resolving the obligation on every terminal path as required.

Test: `crates/roundtable/tests/engine.rs:319` `a_busy_seat_failing_or_crashing_after_end_does_not_strand_the_ratings` — both variants (r1: prompt `fail:true` after End; r2: harness exits) assert `table.is_ended()` without a second End and that Bo/Cy rate. r1 asserts Ada (failed but present) is asked and rates; r2 asserts Ada (gone) does not. Exactly the required scenarios.

## F04 — Cancellation misses descendants after shell exit — FIXED

Fix: `adapters/openrouter-acp/src/tools.ts:277-286` `kill()` signals the process group `-child.pid` unconditionally (no `exitCode` check), so a background descendant holding pipes after the leader exits (FINDINGS scenario `sleep 30.123456789 & exit 0`) is still reached. Only `ESRCH` is swallowed (group already gone). Settlement is on `close` (:292), after leader exit + pipes drained, so abort no longer leaves the promise pending until the descendant exits on its own. Comment :269-276 documents the ID-reuse safety argument.

Test: `adapters/openrouter-acp/test/adapter.test.ts:592` `stopAfterLeaderExit`, run twice: session/cancel (:655-657) and client disconnect via `abortAll` (:659-661). It is the exited-leader case: the shell runs `exit 0` (:601) while a background job holds the pipes; the harness waits until the leader is reaped (ESRCH at :622-626) and only then cancels, and asserts the turn ends `cancelled`. This is exactly the FINDINGS-required coverage, so F04 is FIXED. (BalmyBoron's PARTIAL reasoning cited the live-leader test at :558; that is a different test and is not the one covering F04.)

## F05 — Listed OpenRouter adapter fails creation-time resolution — FIXED

Fix: `crates/roundtable-web/src/tables.rs:60-64` `catalog()` is now the single source: `autoselect` entries + `openrouter_adapter()` inserted at index 0. Listing (`app.rs`) must use the same `catalog`, and creation (:95-99) resolves the submitted ID by scanning `catalog(...)` — not autoselect alone — returning `unknown harness` otherwise. The exact local spec is shared: `openrouter_adapter` (:66-83) builds `LaunchSpec::new("node", [script])` (command + argv vector), fixing the unquoted-path-with-spaces sub-issue; a missing `dist/index.js` yields `available:false` with an explicit `npm run build` note instead of a silent wrong resolution.

Test: `tables.rs:150` `openrouter_adapter_is_launchable_or_says_why` asserts ID, `node` command, argv path ending `adapters/openrouter-acp/dist/index.js`, or the unavailable+note branch. Caveat (same class as F01): it tests the entry, not a full POST-/api/tables round-trip against a mocked registry. Structure (shared `catalog`) makes the GUI path and creation path the same function, so the trace is sound, but no mocked-registry integration test was found. Accept as FIXED on structure + unit test; note the missing end-to-end test.

## F19 — Opt-in provider key removed again at process launch — FIXED

Fix: two coordinated changes. (1) `crates/roundtable/src/config.rs:43-49` — when `share_openrouter_key` and a key is present, insert `OPENROUTER_API_KEY` into `launch.env`. It is deliberately left in `launch.env_remove` (:36-41), so the pair (remove + set) is the opt-in signal. (2) `crates/acp-host/src/process.rs:65-70` — `env_remove` is applied to the inherited environment *before* `.envs(&spec.env)`, so the explicit key wins. All other secret removals are preserved. This is the correct reconciliation: no invention, just fixing the precedence bug.

Test: `crates/acp-host/src/process.rs:199` `explicit_env_wins_over_removal` spawns a real child and reads `shared` (plus `unset` for removal-only). `crates/roundtable/tests/config.rs:26` `an_opted_in_seat_gets_only_the_openrouter_key` asserts the opt-in seat gets exactly the OpenRouter key and not the other secrets, and (per BalmyBoron R2-2 cross-check) the opt-out path. Sharing on/off and "existing inherited key" cases are covered by the pair. Matches FINDINGS' required test shape.

## New defects introduced by the fixes

None found in the four items scoped. F03's `settle_rating` removes a non-Ready seat's obligation via `rating_done` — consistent with on_rating/on_failed handling of a gone seat, and r2's assertion (`!from.contains("Ada")` after exit) confirms no phantom rating is demanded. F04's unconditional `SIGKILL` to `-pid` could in principle hit a reused PGID, but the in-code argument (kernel does not reuse the group ID while members remain, and `close` only fires after pipes are done) is sound for the F04 scenario; worth the F04 test caveat above, not a new defect.
