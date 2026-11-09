# Resolution of the critics' findings

Critics: Sonnet (Claude Code, `sonnet`) and Sol (Codex, `gpt-6.1-sol`), seated in a Roundtable
run on this implementation on 2026-11-05 (record `~/.roundtable/tables/t1a1ae3398b7/record.jsonl`).
Their findings are in `FINDINGS.md`, `Sonnet.md` and `Sol.md`; they changed no source (checked
against a snapshot). This file maps every finding to what was done and how it is verified.

Verification: `cargo test --workspace` (31 tests) and `cargo clippy --workspace --all-targets`
(clean), plus a live run with real Claude Code and Codex seats (record `t1e3688c3c1f1`).

## Priority 1

| # | Finding | Resolution | Verified by |
|---|---|---|---|
| 1 | Chair API and launcher unauthenticated (S1, W1) | Every `/api` route needs a per-run chair token (32 random bytes; `Authorization: Bearer`, or `?token=` for the event stream). Every request must name this server in `Host`, and in `Origin` when sent (defeats DNS rebinding). Non-loopback `--host` warns. The URL with the token is printed at start and the page keeps it per tab. | `app.rs` test `the_chair_api_needs_the_token_and_this_host`; live: no token gets 401 |
| 2 | ScopePolicy symlink escape (H1) | Resolve the deepest existing ancestor, re-append the rest, refuse `.`/`..` in the unresolved part; refuse relative paths with no known cwd. | `permission.rs` tests `scope_rejects_escapes_through_symlinks`, `scope_allows_inside_and_rejects_escapes` |
| 3 | Shell and no-location requests unscoped; non-asking harnesses bypass (H2) | No command-string heuristics (per Sol). A seat whose `mode` fails to apply does not start (fail closed). A seat with no mode set gets a visible warning that the scope may not be enforced for it. Codex uses its `workspace-write` OS sandbox; Claude uses Manual mode so requests reach the policy. Documented limit: an allowed shell command is not confined by the policy. | `engine.rs` `start_seat`; IMPLEMENTATION.md |
| 4 | Bus order discarded by the engine (S3, E2) | The engine consumes one ordered tap and downcasts; four racing subscriptions are gone. | `work_declared_then_finished_in_one_backlog_is_never_a_contribution` |
| 5 | Seat setup stalls the table, including End (S2, H4) | Each seat starts in its own task and reports back; commands run during setup; ready seats take turns at once. `session/new` and setting changes have a 120 s bound. | live run: Sol took the floor before Sonnet was ready |
| 6 | `advance` during a turn corrupts floor and topic (S4, E3) | Floor ownership by seat and prompt (only the owner releases it). `advance` is applied when the floor is free. Each reply keeps the topic its prompt was sent under for judging and numbering. | `advance_during_a_turn_waits_for_the_floor_and_keeps_the_reply_on_its_topic` |
| 7 | Huge window panics the engine (W2) | Window clamped to 5 s to 24 h in the core (config and `SetWindow`). The engine task is supervised: a panic publishes `TableEnded` and shuts the harnesses down. | `config.rs` `clamp_window`; `engine.rs` `spawn` |
| 8 | Contribution beginning "Work" taken as WORK (E1) | First line must be exactly `WORK` or `WORK:`. Prompts say so. | `rules.rs` tests (`Work plan`, `Workflow`, `work`) |
| 9 | JEV awaited inline in the event loop (S9, E8) | Judgments and topic scoring run as tasks that report back; one judgment in flight keeps order; the floor waits for the judgment, commands do not. | `a_jev_timeout_shares_the_contribution_unjudged`, `jev_vetoes_below_070_accepts_at_070_and_explains_at_the_next_turn` |

## Priority 2

| # | Finding | Resolution | Verified by |
|---|---|---|---|
| 10 | SSE history/live handoff loses events (S5) | One hub holds history and live subscribers under one lock; a stream gets a snapshot and registration atomically. `?table=` filter. | `a_stream_opened_mid_flight_gets_every_event_exactly_once` (3,000 concurrent events) |
| 11 | Core accepts invalid configs (S10) | `TableConfig::validate` in the core; `spawn` returns `Result`; the web host reuses it. | `the_core_rejects_invalid_configurations` |
| 12 | Prompt state consumed before send succeeds (E5) | `turn_prompt` builds without mutating; `commit` runs only after `prompt()` returns Ok. | code (`turn.rs` `Commit`) |
| 13 | Topic-poll replies unclassified (E6) | Poll replies are classified; PASS, WORK and empty are no proposal; grapheme-safe truncation. | `a_pass_is_not_a_topic_proposal_and_a_lost_seat_leaves_the_table_running` |
| 14 | Partial first round after a topic change counts (E4) | Rounds count opportunities; a topic change restarts the round. | `rules.rs` / engine tests |
| 15 | Table never ends when all harnesses exit (E7) | `TableEnded { reason: "no participants left" }`. | `the_table_ends_when_every_participant_is_gone` |
| 16 | Process tree not killed (M1) | The harness is its own process-group leader; shutdown sends SIGTERM to the group, SIGKILL after 3 s, and the group is killed when the leader exits. | `shutdown_ends_the_whole_process_group`; live: no adapter processes after End |
| 17 | Millisecond table ids collide (S6, W6) | Random 48-bit ids from the OS random source. | `tables.rs` |
| 18 | Seat names not URL-encoded; `__proto__` in the UI (S7) | Core-validated names; tools URLs built with a path-segment encoder; the page keeps user-keyed data in `Map`s. | `the_core_rejects_invalid_configurations`; `index.html` |
| 19 | Headless `run` ignores bind failure (S8) | Bind before anything; fail immediately; the run stops if the server stops. | `main.rs` |
| 20 | Feedback unvalidated (S11, W4) | Known participant, no self-rating, integers 0 to 5, boolean bonus, note up to 1,000 chars; rejected calls return `isError`; nothing is acknowledged after the table ends. Re-checked in the engine. | `feedback_is_validated_and_recorded`; live: both harnesses recorded feedback |
| 21 | History unbounded; all tables visible; ended tables kept (W3) | Streamed reply chunks are live-only (the completed reply carries the text); per-table stream filter; ended tables are removed so their tools and commands stop working. The rest of the history is kept in memory for the run (documented). | `app.rs` |
| 22 | Tools token: not CSPRNG, plain compare, in URL path (W5, M5) | 32 random bytes from the OS; constant-time compare; sent in an `Authorization` header via ACP `McpServerHttp.headers`, no longer in the URL. | live: Claude Code and Codex both called `feedback` with the header |
| 23 | Registry env and secrets inheritance (H3, narrowed) | Registry entries cannot set `PATH`, `LD_*`, `DYLD_*`, `NODE_OPTIONS`, `NODE_PATH`, `PYTHONPATH`, `PYTHONSTARTUP`, `BASH_ENV`, `ENV`, `HOME`, `NPM_CONFIG_*`. Roundtable's secrets (`OPENROUTER_API_KEY`, `TYPESAFE_API_KEY`) are removed from every agent unless the seat opts in (needed for Pi). All built-in versions pinned. | `launch.rs` test `registry_cannot_set_loader_or_path_variables`; `engine.rs` `start_seat` |
| 24 | Test gaps (S12) | Added: fake-JEV boundary (0.69 / 0.70), timeout fail-open, veto explained next turn, required work skip, ordered backlog, advance mid-turn, exit mid-turn, all exited, PASS in poll, config validation, feedback validation, `Harness` tests in acp-host (reply ordering, one turn per session, permissions, exit mid-turn, process group), router auth, stream handoff. | 31 tests |

## Open and narrowed items

| Item | Resolution |
|---|---|
| H4 second half (settings failures) | Agreed compromise implemented: a failed `mode` keeps the seat out; other settings warn and continue. |
| M2 exit mid-prompt | Verified and fixed in acp-host: exactly one `PromptFailed`, before `HarnessExited`. Test `an_exit_mid_turn_fails_the_prompt_once_before_the_exit_event`. |
| M3 text/completion ordering | Verified against the SDK with a test: a chunk sent immediately before the response is in the reply (`reply_is_complete_and_one_turn_runs_per_session`). |
| M4 last-block reply | Kept (Sol's position): the reply is the text after the last tool call, and the participant prompt now says so. Open for the owner if pre-tool text should count. Test `the_reply_is_the_text_after_the_last_tool_call`. |
| L items | Done: event JSON cached per event; unique event names asserted in debug builds; stderr reader joined instead of a sleep, lines capped at 2,000 bytes; one-time permission options preferred and a standing option is noted when it is the only one; an allow with no allow option becomes a reject, never "cancelled"; JEV questions mark participant text as untrusted. Not done: lazy pruning of dead subscribers stays (harmless); non-text agent chunks are still ignored. |

## Found during the critics' run (builder)

While one critic worked and the other passed, the original round rules counted those rounds as
"all pass" and nonproductive, so topics churned to the idle seat's proposal every two rounds.
Fixed: a round with independent work in it is not nonproductive, and "all participants pass"
needs every participant that took part to have passed (README 1.3, 4.4, 6). Test in `rules.rs`.
