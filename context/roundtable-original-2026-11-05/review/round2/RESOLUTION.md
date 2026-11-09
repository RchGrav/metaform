# Round 2 resolution

Builder's record of what was changed for each agreed finding in `FINDINGS.md`. This is not authority (see the authority order in `FINDINGS.md`). Round 3 (`review/round3/`) verifies it. All Rust tests pass and `cargo clippy --workspace --all-targets` reports nothing. The adapter (`adapters/openrouter-acp`) passes `npm test`, 25 of 25.

| ID | Status | What changed | Proof |
|---|---|---|---|
| F01 | Fixed | `ROUNDTABLE_TOKEN` added to `SECRET_ENV`. Seat environments are built by `SeatConfig::launch_spec` (`config.rs`), which strips every secret, including explicit ones; only `OPENROUTER_API_KEY` can come back, by opt-in. | `tests/config.rs` (both tests) |
| F02 | Fixed (Rust and adapter) | Rust: `permission.rs` `resolve()` follows a dangling symlink to its target, up to Linux's `MAXSYMLINKS` (40). It refuses on any error other than not-found, so loops are refused. Adapter: `resolveReal` follows dangling links using kernel `..` semantics. Reads and writes open with `O_NOFOLLOW`, and paths are re-checked at write time. | `permission.rs` `scope_follows_dangling_symlinks`; adapter tests at `adapter.test.ts` ~406/453/495 |
| F03 | Fixed | `settle_rating()` (`engine.rs`) runs on every way a prompt ends: completed, failed, crashed. It asks a surviving seat that is now free and wasn't asked yet, or drops a gone seat from the round. `rating_done` ends the table once, and only when it removed a seat. | `a_busy_seat_failing_or_crashing_after_end_does_not_strand_the_ratings` (fail and crash variants) |
| F04 | Fixed (adapter) | Cancel sends SIGKILL to the whole process group even after the shell has exited; ESRCH means already stopped. The command settles once its pipes close. | adapter `stopAfterLeaderExit`, run for both cancel and disconnect |
| F05 | Fixed | `tables::catalog()` is the one resolver for listing and for table creation. The adapter launches as a command plus an argument list, so a path with spaces works. A missing build is listed as unavailable, with the reason. | `catalog_tests::openrouter_adapter_is_launchable_or_says_why` |
| F06 | Fixed | `Polling.asked`: a proposal counts only from a seat asked in the current poll, and only before scoring starts. Late replies get a notice. | `a_late_proposal_does_not_enter_a_decided_poll` |
| F07 | Fixed | `settings_changed()` stops a poll in progress and drops a queued `advance` once topics lose JEV. `step()` rechecks eligibility before applying an `advance`. | `turning_judging_off_mid_poll_stops_topic_selection` |
| F08 | Fixed | `update_profile()` (`app.rs`) creates a profile only when the file is missing; a read or parse error, or a malformed shape, is an error. Writes go to a temporary file renamed over the original. Failures appear as a table notice. | `identity_profiles_are_never_silently_replaced` |
| F09 | Fixed | `record::harness_id`/`table_of` accept `{pid, id}`. The page's `harnessId()` does the same and shows AgentSight status and observations. The engine raises a loud notice for every `monitor.unavailable`, at attach and later. | `record::tests::monitor_events_route_to_their_table`; the critics' `monitor-routing.mjs`, re-run with the new helper (output in this session) |
| F10 | Fixed | SSE keepalive removed. History refreshes on the `roundtable.ended` event itself. No `setTimeout` or `setInterval` remains in the page. | grep; page check |
| F11 | Fixed | Feedback must name exactly one other participant, or the sender is told at its next turn and the chair sees a notice. Feedback is saved to the identity's `feedback` list (no points) and to `accolades.jsonl`, and save failures appear as table notices. The tool text says only what happens. | `advance_is_refused_truthfully_without_jev` (feedback part); `identity_profiles_are_never_silently_replaced` |
| F12 | Fixed (prompt) | The tools line is sent only to seats that have the tools (`Seat.tools`). Seats on OpenRouter models now run on OpenCode, which supports MCP, so they get the tools too. The repository adapter still has no MCP. | `the_first_turn_carries_the_owners_prompt_with_placeholders_filled` (no tools line without tools); `a_seat_with_tools_is_told_about_them` (added after round 3 flagged the gap) |
| F13 | Fixed | A review request ends with the owner's allowance line. | assertion in `a_lone_free_agent_is_asked_to_review_once_while_the_other_works`, now with a base of 700 (round 3 asked for a nondefault bank) |
| F14 | Fixed | An empty proposal is reported (`TurnFailed` plus an error notice). A rating reply that leaves out peers (`{}` or a partial set) gets an error notice naming them; the rater is not asked again. Round 3 graded this PARTIAL before the ratings half landed. | `missing_peer_ratings_are_reported` |
| F15 | Fixed | An after-work acceptance with judging off or no key calls `record_accept()` once (`resolve_reply`). | code only; no isolated test |
| F16 | Fixed | The page takes the base from `roundtable.opened` and resets to it after acceptance. | page code |
| F17 | Fixed | "privately" removed. | — |
| F18 | Fixed | Failed and gone seats are left out of the participant list. | `a_failed_seat_is_not_listed_as_joining` |
| F19 | Fixed | `acp-host` applies removals to the inherited environment before setting explicit variables. | `process::tests::explicit_env_wins_over_removal`; `tests/config.rs` |

## Also changed in this pass (owner instructions, not findings)

- **Participant prompt:** the owner's new template (2026-11-05) is used verbatim from `crates/roundtable/resources/participant_prompt.md`. `{{roundtable_prompt}}` is the objective and `{{char_max}}` the table's base allowance. The objective is no longer repeated as the first "Current topic". My mechanics block keeps only names and turn order, PASS, working, topics and (per seat) tools; the template's own text covers electing a head of the table and scoring.
- **Harness catalog:** a registry harness that is distributed only as a binary but is already installed (OpenCode) runs from PATH with the registry's arguments, and its version difference is noted. Test: `installed_registry_binaries_are_launchable`.
- **Page:** each seat shows "Prompts received", the exact text every agent was sent.

## Open

- **F15:** the immediate-acceptance-then-settings-toggle scenario has no isolated test (round 3 noted this).
- **OpenCode seats:** catalog OpenCode seats now get `OPENCODE_CONFIG_CONTENT` with every permission set to "ask", so Roundtable's workspace policy decides (verified live: a write outside the workspace was asked for, refused, and not made). Round 3's OpenCode seats started before this change, so the workspace limit was not enforced for them.
- **Adapter, F04 limit:** a background job that leaves the process group with `setsid` while holding the pipes can still keep a command pending. This needs a choice: destroy the pipes on abort (the turn ends; the escaped process keeps running), or track processes by cgroup.
- **Adapter, F02 limit:** `O_NOFOLLOW` protects only the last component of a path. A parent directory swapped between the check and the open needs `openat2(RESOLVE_BENEATH)`, which Node doesn't expose.
- **Owner-open items** from `FINDINGS.md`: shutdown wait policy, `advance` deferral, security hardening, rating carry-forward, whether feedback stays, context handoff, TASTE, ties of three or more.
