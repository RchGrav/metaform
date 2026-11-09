# Roundtable traceability matrix

Every requirement in the owner's specification (`README.md`, cited as R §n) and ACP integration design (`Roundtable_ACP_Integration_Design.md`, cited as D §n), plus the owner's direct decisions (cited as O), mapped to what the code does now.

- **Statuses (sections A-K):**
  - DONE: the code does what the requirement says. The Test column names the proving test, or "none" when the evidence is code only.
  - PARTIAL: part of the requirement is in the code; the cell names the missing part.
  - DIFFERS: the code does something other than the owner text.
  - MISSING: not in the code.
  - REMOVED: an addition or prompt line the code no longer has.
  - OWNER DECISION PENDING: the right behavior depends on an open owner decision (section P, or the open list in N).
- **Older statuses.** Sections L and M use the pre-rewrite terms (VIOLATED, DONE-UNTESTED, INVENTED). They are kept as recorded.
- **"Test"** names only tests that check the requirement itself.
- **Code state:** sections A-K were refreshed in place on 2026-11-05 against the working tree. Sources: the read-only audit `review/AUDIT-OWNER-DESIGN.md` (cited as audit D# = differs, M# = missing, B# = builder addition, Q# = open question), spot-checked in the code; `review/round2/RESOLUTION.md`; `review/round3/VERDICTS.md`.
- **Tests were not run for this refresh.** No table was started. Pass results come from `review/round3/VERDICTS.md` (all Rust tests green; adapter `npm test` 25 of 25). Code changed after round 3 might not be covered by that run.
- **Paths:** an unqualified file is in `crates/roundtable/src/`. `acp-host/` = `crates/acp-host/src/`; `web/` = `crates/roundtable-web/src/`; `index.html` = `crates/roundtable-web/assets/index.html`; `agent-monitor/` = `crates/agent-monitor/src/`; `adapter.ts` = `adapters/openrouter-acp/src/adapter.ts`. TPL = `crates/roundtable/resources/participant_prompt.md`. Engine tests are in `crates/roundtable/tests/engine.rs`, rules tests in `crates/roundtable/tests/rules.rs`, acp-host tests in `crates/acp-host/tests/harness.rs`.

## A. The discussion loop (R §4, D §2)

| ID | Requirement | Code now | Test | Status |
|---|---|---|---|---|
| A1 | R §4.1 Every participant begins with a 512-character allowance; it is told its allowance before contributing | The base allowance is a chair setting, default 512 (`rules.rs:8`, `config.rs:122`). TPL states it through `{{char_max}}` (`prompts.rs:13-16`). Every turn ends with "You have {n} Characters to Respond" (`turn.rs:55`). | rules: `allowance_uses_the_chairs_base_credits_once_and_resets`; engine: `the_first_turn_carries_the_owners_prompt_with_placeholders_filled` | DONE |
| A2 | R §4.1 The allowance applies to discussion messages, not workspace artifacts | Only the discussion reply is cut to the allowance (`turn.rs:100-105`). Workspace files are not touched. Topic proposals have their own fixed 512 limit (`rules.rs:12`; audit B15). | none | DONE |
| A3 | R §4.2 A contribution is evaluated by JEV before distribution; accepted ones join the discussion | `submit` sends the truncated text to JEV (`turn.rs:98-136`). `on_judged` shares it only when all three checks pass (`turn.rs:138-184`). With judging off or no key it is shared unjudged (`turn.rs:107-114`; owner B6). | engine: `a_vetoed_truncated_agent_gets_the_owners_format_at_its_next_turn` | DONE |
| A4 | R §4.3 Passing declines to contribute; every pass credits +512 | `classify` reads a pass in any case, with trailing dots (`rules.rs:78-86`; audit B14). A pass earns one base credit only when another agent's message was accepted since this agent's last outcome (`rules.rs:64-66`, `engine.rs:352-359`). TPL:15 promises credit for every pass. | rules: `replies_are_pass_contribution_or_empty`; `allowance_uses_the_chairs_base_credits_once_and_resets` checks the conditional rule, not the requirement | DIFFERS (audit D3, Q1; P1) |
| A5 | R §4.4 "While the agent is occupied with independent work, the discussion continues without waiting for it." | An agent is working when ACP reports tool activity during its floor turn (`engine.rs:581-600`). The floor is released at once and the table moves on. The reply when the agent finishes is judged as its message (`engine.rs:602-630`). | engine: `tool_activity_marks_an_agent_working_and_the_table_moves_on` | DONE |
| A6 | R §4.4 The agent is skipped during its occupied turns; each skipped turn credits +512 | A working seat is skipped in turn order (`engine.rs:473-521`, `give_floor`). A skip earns one credit only when something new was accepted, as in A4. An agent that starts working on its own floor turn gets no credit for that turn (`engine.rs:588-590`; audit B22). | engine: `tool_activity_marks_an_agent_working_and_the_table_moves_on` (asserts `credited: false` with nothing new) | DIFFERS (audit D3, D9; P1) |
| A7 | R §4.4 Independent work must not be interpreted as an instruction to abandon or terminate the agent's work | Nothing cancels a busy agent. `Harness::cancel` (`acp-host/harness.rs:588`) has no caller in Roundtable. No timer acts on agents. | engine: `tool_activity_marks_an_agent_working_and_the_table_moves_on` (the working agent finishes) | DONE |
| A8 | R §4.5 Oversized messages are truncated to the allowance, not rejected for length | `truncate` cuts at a grapheme boundary and counts Unicode scalar values (`rules.rs:39-58`; audit B38). Length never rejects. | rules: `truncation_reports_characters_lost_at_grapheme_boundaries` | DONE |
| A9 | R §4.5 The truncated message goes to JEV, and the participant is told at its next turn that it was truncated and how many characters were removed | The truncated text goes to JEV (`turn.rs:100-106`). The notice "Message went past your {limit} Character Limit, {n} Characters Lost" (`prompts.rs:38-40`) is queued for the next prompt. | engine: `a_vetoed_truncated_agent_gets_the_owners_format_at_its_next_turn` (exact wording and count) | DONE |
| A10 | R §4.6 A veto withholds the contribution and does not credit the allowance | A veto publishes the contribution as not accepted and leaves the allowance unchanged (`turn.rs:163-181`). | engine: `a_vetoed_truncated_agent_gets_the_owners_format_at_its_next_turn` | DONE |
| A11 | R §4.6 The participant is not immediately given another chance; it is told the disposition and the reason at its next turn | The veto notice is queued (`turn.rs:165`) and flushed into the seat's next prompt of any kind (`turn.rs:41`, `commit` at `turn.rs:59-65`), including a topic-proposal or rating request (audit D7). The reason is the failed check question plus JEV's confidence, in a builder sentence (`prompts.rs:53-57`; audit D5). | engine: `a_vetoed_truncated_agent_gets_the_owners_format_at_its_next_turn` (next floor prompt only) | DIFFERS (audit D5, D7) |
| A11b | R §4.7 order: step 2 pending feedback, then step 3 allowance and discussion context | `turn_prompt` keeps the owner's four items in order: truncation, veto, messages, allowance (`turn.rs:24-57`). It also adds "Current topic:" between the notices and the messages (`turn.rs:44-47`), "Chair:" lines among the messages (`turn.rs:51`), and an "[R1-2] Name: " prefix (`turn.rs:50`). | engine: `a_vetoed_truncated_agent_gets_the_owners_format_at_its_next_turn` (asserts the four-item order) | DIFFERS (audit D6) |
| A12 | R §4.6 / D §2 item 8: no disposition message for a simple acceptance | An acceptance queues no notice (`turn.rs:186-209`). | none checks the absence | DONE |
| A13 | R §4.7 The loop runs in nine steps, in order, for each participant in turn | Turns run one at a time in seat order (`engine.rs:473-521`). The next turn waits for JEV's answer on a floor contribution (`engine.rs:453`, `turn.rs:125-127`; audit B21, Q6). Step 5 crediting differs: see A4 and A6. | engine: `a_vetoed_truncated_agent_gets_the_owners_format_at_its_next_turn` (floors Ada, Bo, Cy in order) | DONE |
| A14 | R §4.7 "Agents performing independent work do not prevent the rest of the Roundtable from progressing." | A working agent releases the floor and the table continues (A5). A polled seat that starts working is no longer waited for (`engine.rs:591-596`). | engine: `tool_activity_marks_an_agent_working_and_the_table_moves_on` | DONE |
| A15 | O: "if everyone is busy the table has to wait. if only one is free the table should wait." | `MIN_FREE_TO_DISCUSS = 2` (`engine.rs:30`). `give_floor` waits while fewer than two seats are free (`engine.rs:476-487`). | engine: `a_lone_free_agent_is_asked_to_review_once_while_the_other_works` | DONE |
| A16 | O: "if one agent is idle and the others are busy it should be told to review materials" | The lone free agent gets the review request once per idle period (`engine.rs:523-531`, `prompts.rs:69`). Its reply is judged as a contribution. The wording is the builder's (audit B11). | engine: `a_lone_free_agent_is_asked_to_review_once_while_the_other_works` (exactly one review; ends with the allowance line) | DONE |
| A17 | O: "we need at least two agents to have a debate" | As A15. With one seat left, the chair sees an error notice (`engine.rs:481-484`). | engine: `a_lone_free_agent_is_asked_to_review_once_while_the_other_works` | DONE |

## B. JEV (R §5, D §1)

| ID | Requirement | Code now | Test | Status |
|---|---|---|---|---|
| B1 | R §5.1 Three conditions: new or a position on a recent matter; value; relevance | The owner's three checks, verbatim from `archaeology/roundtable-jev-checks.md` (`jev.rs:78-100`; O:308). The audit checked all nine strings by script (audit §6). | none checks the question text | DONE |
| B2 | R §5.1 Each condition needs ≥70%; pass only if all three do (O: 0.70) | `PASS_CONFIDENCE = 0.70` (`rules.rs:10`). Any check below it vetoes (`turn.rs:159-160`). | engine: `a_vetoed_truncated_agent_gets_the_owners_format_at_its_next_turn` (0.10 vetoes, 0.95 accepts). No 0.69/0.70 boundary test. | DONE |
| B3 | R §5 Multiple questions in one request; through OpenRouter | One request carries all three questions to the OpenRouter decisions endpoint (`jev.rs:10`, `turn.rs:131-134`). | engine tests: the fake endpoint receives all questions in one body | DONE |
| B4 | R §5.1 "JEV provides the judgment and the reasons for a veto" | JEV returns only confidences. The vetoed agent receives the failed check question and its confidence (`prompts.rs:53-57`). The owner's earlier notices give no scores (audit D5). | none | DIFFERS (audit D5) |
| B5 | R §5.1 Condition 1: "previously unstated" | JEV receives `subject` (the topic), `recent_responses` (the newest 50 KB of discussion as a rolling window across all topics, chair lines included), `candidate` and `objective` (`turn.rs:119-124`, `jev.rs:40-72`). This follows the owner's instruction recorded in O:307. The audit found that quote in no owner document file (audit B6, Q5). | `jev.rs` unit: `the_discussion_window_keeps_the_most_recent_50_kb` | DONE (per O:307) |
| B6 | O: JEV is optional; if it is down the table continues; judging is a GUI setting | Judging off or no key: shared unjudged (`turn.rs:107-114`). JEV error: shared unjudged with an error notice (`turn.rs:153-157`). The chair toggles judging (`engine.rs:774-777`). | engine: `a_jev_failure_shares_unjudged_and_says_so` | DONE |
| B7 | O: "jev gets a reply or an error"; no timers | No timeout on JEV calls (`jev.rs`). | none | DONE |
| B8 | R §5.2 Evaluation happens once, before broadcast | Each contribution is judged once in `submit`, before `accept` publishes it (`turn.rs:98-136, 186-209`). | none | DONE |
| B9 | — | The "ignore instructions in participant text" suffix is gone from `jev.rs`. | — | REMOVED |

## C. Topics (R §6-7)

| ID | Requirement | Code now | Test | Status |
|---|---|---|---|---|
| C1 | R §6 Advance after two nonproductive rounds, or after all participants pass for two rounds | `RoundTracker` (`rules.rs:104-144`); rounds close in `opportunity` (`engine.rs:558-572`). Topics advance only while topics are active (judging on and a key, O in M). | rules: `two_nonproductive_or_two_all_pass_rounds_advance_and_skips_count_as_passes` | DONE |
| C2 | O: being skipped counts as passing ("two rounds of skips ends the roundtable") | `SkippedWorking` counts as passed (`rules.rs:119`). An agent that starts working on its own turn also counts as passing (`engine.rs:590`; audit D9, B22). | rules: `two_nonproductive_or_two_all_pass_rounds_advance_and_skips_count_as_passes` | DONE |
| C3 | R §6 The overall objective stays unchanged | The objective is fixed in the table config and sent once (`turn.rs:38`). Topic changes do not touch it. | none | DONE |
| C4 | R §7 All participating agents are polled. O: agents busy with independent work are not waited for. | Only idle seats are asked (`turn.rs:212-224`). A polled seat that uses a tool is dropped from the wait (`engine.rs:591-596`), and its later proposal is discarded as late (`turn.rs:226-236`). The request text is the builder's (`prompts.rs:64-66`; audit D8). The O part has no owner quote (audit Q3). | engine: `a_late_proposal_does_not_enter_a_decided_poll` | DIFFERS (audit D4, D8, Q3; P2) |
| C5 | R §7.1 JEV judges same underlying intent, not similar words | Each pair is asked "Do proposal A and proposal B express the same underlying intent?" (`jev.rs:103-109`). The criteria text is the builder's (audit B8). An archaeology file asks for similarity instead (audit Q2). | engine: `topics_need_jev_and_follow_the_selection_rules` (pair asked; wording not checked) | DONE (per R §7.1; P3) |
| C6 | R §7.2 Each unique pair is evaluated once | `pairs` (`rules.rs:174-176`). | rules: `topic_selection_follows_the_readme_example` | DONE |
| C7 | R §7.3 Each pair's confidence is credited to both proposals and summed; the highest wins; no threshold | `select_topic` (`rules.rs:150-171`). | rules: `topic_selection_follows_the_readme_example` | DONE (per R §7.3; P3) |
| C8 | R §7.4 Two tied proposals are joined with "and" | Tied winners join with " and " (`rules.rs:162-168`), in seat order (`turn.rs:256-259`). | rules: `topic_selection_follows_the_readme_example`; engine: `topics_need_jev_and_follow_the_selection_rules` | DONE |
| C9 | — | Three or more ties all join (`rules.rs:162-168`; audit B16). Unjudged pairs no longer occur, because topics require JEV (M; `engine.rs:325-327`). | rules | OWNER DECISION PENDING (audit Q13) |
| C10 | — | The fixed 512-character cut stays (`rules.rs:12`, `turn.rs:242`; L K#6, M). It does not follow the chair's base (audit B15). The "private" label is gone (`prompts.rs:64-66`; round 2 F17). | — | REMOVED ("private"); the limit is kept per L K#6 |
| C11 | R §7.6 The 30K-token case alternative is not a replacement | Not implemented. | — | DONE |

## D. Continuity (R §8, R §1.5)

| ID | Requirement | Code now | Test | Status |
|---|---|---|---|---|
| D1 | Topic changes do not reset agents' context; the same ACP sessions continue | Each seat opens one session at start (`engine.rs:880`) and keeps it for every topic. The participant prompt is sent once (`turn.rs:27-40`). | engine: `the_first_turn_carries_the_owners_prompt_with_placeholders_filled` | DONE |
| D2 | Participants keep the objective, earlier discussion, decisions and workspace | Each prompt carries only what is new (`turn.rs:48-54`); the ACP session keeps the rest. Sessions do not carry across tables (audit M4). | none | DONE |
| D3 | — | `change_topic` does not touch allowances (`turn.rs:315-333`). L K#3 adds no rule. | none | DONE (no rule, per L) |

## E. Prompt (R §3, R §11)

| ID | Requirement | Code now | Test | Status |
|---|---|---|---|---|
| E1 | R §3 The participant prompt is given verbatim, with the objective and current context | The owner's 2026-11-05 template supersedes the R §3 wording (O:302). It is sent verbatim, once, with `{{roundtable_prompt}}` and `{{char_max}}` filled (`prompts.rs:10-16`, `turn.rs:38`). R §3 and D §2 still carry the old text (audit Q10). | engine: `the_first_turn_carries_the_owners_prompt_with_placeholders_filled` | DONE |
| E2 | R §3 The system supplies the allowance, feedback, context and current topic | Allowance, feedback and context arrive each turn (`turn.rs:41-55`). The topic line is sent only while topics are active (`turn.rs:45`), so with JEV off a chair-given first topic never reaches the agents (audit D10). | none | DIFFERS (audit D10) |
| E3 | O: the prompt explains the process, suggests electing a head of the table, and offers the tools | TPL suggests electing a head. The builder's mechanics block (`prompts.rs:21-35`) adds turn order, PASS, working, topic rules and, for seats with tools only, the tools (round 2 F12). Four statements in it do not match the code: "exactly PASS" (B14), "each free participant proposes" (D4), the topic-end paraphrase (D9), and accolades that do not exist (M5). | engine: `a_seat_with_tools_is_told_about_them`; `the_first_turn_carries_the_owners_prompt_with_placeholders_filled` (no tools line without tools) | PARTIAL (audit B1, D4, D9, M5) |
| E4 | — | No "use tools first" line and no `WORK` convention. A reply that starts with `WORK` is an ordinary contribution. | rules: `replies_are_pass_contribution_or_empty` | REMOVED |
| E5 | D §2 note: there is no universal ACP system-prompt setter; use the first prompt | The participant prompt goes in the first `session/prompt` (`turn.rs:27-40`). | engine: `the_first_turn_carries_the_owners_prompt_with_placeholders_filled` | DONE |

## F. ACP (R §9.1, D §4-5)

| ID | Requirement | Code now | Test | Status |
|---|---|---|---|---|
| F1 | D §4 Follow the version negotiated by `initialize`; v2 where supported | Offers v2 first. If the agent selects or requires v1, the host restarts the process on v1 and checks the answered version (`acp-host/harness.rs:186-229`). Preferring v2 and restarting are builder choices (audit B33). | acp-host: `a_v2_agent_negotiates_v2_and_its_turn_ends_on_idle`, `a_v1_only_agent_is_restarted_fresh_on_v1` | DONE |
| F2 | R §9.1 `authenticate` when required | When `session/new` reports that authentication is required, the host uses an advertised agent-run method (`acp-host/harness.rs:349-383`). | acp-host: `authentication_is_completed_then_the_session_opens`, `authentication_that_does_not_help_or_cannot_run_is_an_error` | DONE |
| F3 | `session/new` with the shared cwd and optional MCP servers | `open_session` with the workspace (`acp-host/harness.rs:311`). The Roundtable HTTP MCP server is offered when the agent accepts HTTP MCP (`engine.rs:866-879`). | acp-host tests; live runs (N, O) | DONE |
| F4 | `session/set_config_option` **only when the option is advertised** | Only advertised options are sent; any other id is an error (`acp-host/harness.rs:464-506`). A failed setting is a loud error and the seat still joins (`engine.rs:887-890`). | acp-host: `only_advertised_options_are_set` (v1 and v2) | DONE |
| F5 | `session/prompt` and `session/update` (message chunks, tool calls) | Prompt and update handling for v1 and v2 (`acp-host/harness.rs`). | acp-host: `reply_is_complete_and_one_turn_runs_per_session`, `the_reply_has_the_text_before_and_after_a_tool_call` | DONE |
| F6 | `session/load` / `session/resume` to keep or restore context | `resume_session`: v2 resume; v1 resume, else load (`acp-host/harness.rs:391-425`). Roundtable never calls it: every table opens new sessions (`engine.rs:880`; audit M4). | acp-host: `sessions_are_resumed_or_loaded_without_republishing_history` | PARTIAL (audit M4) |
| F7 | `session/cancel` only when requested | `cancel` exists (`acp-host/harness.rs:588`); nothing calls it automatically. | none | DONE |
| F8 | `session/close` where advertised, to end a session | `shutdown` closes open sessions where advertised, then ends the process (`acp-host/harness.rs:596-615`). The process sequence waits 1 s and 2 s (`acp-host/process.rs:20-27, 128-146`); these timers await the owner (audit D14). | acp-host: `shutdown_closes_open_sessions_then_ends_the_process`, `shutdown_ends_the_whole_process_group` | DONE (close); shutdown timers OWNER DECISION PENDING |
| F9 | `session/request_permission` answered | `ScopePolicy` answers every request. **Safety:** it allows any request that names no path, shell commands included (`acp-host/permission.rs:36-38`; audit B28). It answers `Cancelled` when no option fits (`acp-host/harness.rs:943, 966`). | acp-host: `permissions_inside_scope_are_allowed_once_and_outside_rejected`; unit `scope_allows_inside_and_rejects_escapes`, `scope_rejects_escapes_through_symlinks`, `scope_follows_dangling_symlinks` | DONE (safety note: audit B28) |
| F10 | v2 `state_update` (`running`/`idle`/`requires_action`) used for activity | `state_update` ends a turn on `idle` and is published as `AgentState` (`acp-host/harness.rs:836-886`). The engine does not consume `AgentState`; it uses tool activity (A5). The v2 `background` report is ignored (audit M10). | acp-host: `a_v2_agent_negotiates_v2_and_its_turn_ends_on_idle` | PARTIAL (audit M10) |
| F11 | Transport: newline-delimited JSON-RPC over stdio | SDK byte streams over stdio. | acp-host tests | DONE |

## G. Harnesses and OpenRouter (R §9.2-9.4, D §3, §7)

| ID | Requirement | Code now | Test | Status |
|---|---|---|---|---|
| G1 | R §9.2 Discover published agents through the ACP Registry | `parse_registry` and `autoselect` (`acp-host/launch.rs:93-140, 206`). | acp-host unit: `registry_entries_resolve_npx_uvx_and_binary` | DONE |
| G2 | D §7.1 `acpr` resolves and launches registered agents | npx and uvx launches are rebuilt from the registry. acpr is used only for binary entries that are not already installed (`acp-host/launch.rs:103-131`). | acp-host unit: `registry_entries_resolve_npx_uvx_and_binary`, `installed_registry_binaries_are_launchable` | DIFFERS (audit D16) |
| G3 | R §9.2 Locally installed or unregistered ACP commands are usable | Custom command line (`acp-host/launch.rs:227-230`). | acp-host unit: `command_lines_split_on_whitespace_and_respect_quotes` | DONE |
| G4 | R §9.3 Claude Code, Codex, Pi, OpenCode, others | Built-in entries with pinned versions (`acp-host/launch.rs:85-88`; audit B32). Claude Code and Codex ran live (N). OpenCode ran live in round 3 (O). Pi never ran; the owner did not use it because pi-acp does not wire MCP (O). | live runs | PARTIAL |
| G5 | R §9.4 An OpenRouter key can be supplied | From the environment or the page, held in memory (`web/app.rs:119, 219-221`). **Safety:** agents get it only by opt-in, which the page ticks for some harnesses (`config.rs:28-55`, `index.html:426-428`; audit B29). | config: `an_opted_in_seat_gets_only_the_openrouter_key` | DONE |
| G6 | R §9.4 Select participants by OpenRouter model id; models come from the published catalog, not a fixed list | The page loads `/api/models` for OpenRouter seats (`index.html:412-423`, `web/app.rs:206-213`). The fixed hints are gone. | none | DONE |
| G7 | R §9.4 / D §7.3 The OpenRouter Agent SDK behind an ACP adapter | `adapters/openrouter-acp` wraps the SDK as an ACP agent. It refuses MCP servers (`adapter.ts:190-194`), so its seats have no Roundtable tools. The owner moved OpenRouter models to OpenCode (O:304); the adapter stays first in the catalog (audit B35). | adapter `npm test`, 25 of 25 in round 3 (mocked; no paid calls) | DONE |
| G8 | D §7.3 path 1: Pi + pi-acp with an OpenRouter model | pi-acp is in the catalog, and the page ticks the key opt-in for it (`index.html:426-428`). The route was never run. The owner chose OpenCode for OpenRouter models instead (O:304). | none | PARTIAL |
| G9 | D §3: model selection and harness selection are separate dimensions | The seat config holds the harness and its settings (model) as separate fields. | none | DONE |

## H. Asynchronous operation and AgentSight (R §10, D §8)

| ID | Requirement | Code now | Test | Status |
|---|---|---|---|---|
| H1 | R §10 Agents operate independently; the discussion never waits for one participant's work | As A5. | engine: `tool_activity_marks_an_agent_working_and_the_table_moves_on` | DONE |
| H2 | R §10.2-10.3 / D §8: AgentSight independently observes process, tool, file and network activity | `crates/agent-monitor` attaches AgentSight per harness pid (`engine.rs:707-716`); failures are loud notices (`engine.rs:423-429`). **Safety-relevant:** it needs root and refuses `sudo -n` (`agent-monitor/lib.rs:47-53`), so unprivileged it observes nothing (audit D15). TLS is captured for the harness pid only, and no native session source is used (audit M9). N records verification as root in Boat sandboxes. | `crates/agent-monitor/tests/live_capture.rs`: `python_harness`, `node_harness` (need root) | PARTIAL (audit D15, M9) |
| H3 | D §8 Correlate observations with the ACP process and session | Observations carry the harness pid and the harness id that acp-host uses, and route to their table (`record.rs:24-37`). Session-level attribution is limited by design (D §8). | unit: `record::tests::monitor_events_route_to_their_table` | DONE |
| H4 | R §10.3 No automatic timeout-based termination of busy agents | No timer acts on a busy agent. The only timers are the shutdown waits at End (audit D14). | none | DONE |
| H5 | R §10.4 The absence of an ACP reply is not proof an agent should be terminated | Silence ends nothing; only prompt completion (v1) or `idle` (v2) ends a turn. | none | DONE |
| H6 | R §10.5 / O: an event-driven bus; never poll what can surface as an event | The `bus` crate; the engine consumes one ordered tap (`engine.rs:400-432`). The page refreshes history on the `roundtable.ended` event. No `setTimeout`, `setInterval` or SSE keepalive remains (`web/app.rs:346`; round 2 F10). | `crates/bus/tests/bus.rs`; web unit: `a_stream_opened_mid_flight_gets_every_event_exactly_once` | DONE |
| H7 | O: a crashed agent is a bug: fail loudly, then fix | A harness exit marks the seat gone with an error notice; the table ends when nobody is left (`engine.rs:674-704`). Seat start failures and JEV errors are loud. One silent drop remains in the rating round: a null or non-object peer card (`turn.rs:372-373`; round 3 N01). | engine: `a_crash_is_loud_and_the_table_ends_when_nobody_is_left` | DONE (crashes; N01 is listed in N) |

## I. Owner decisions not covered above

| ID | Decision | Code now | Status |
|---|---|---|---|
| I-1 | Permissions automatic, inside the workspace or across the project; never stuck | `ScopePolicy` on the workspace, or on a scope the chair sets through the API only (`web/tables.rs:20`); the page has no scope field. **Safety:** requests that name no path are allowed, shell commands included (audit B28). Catalog OpenCode seats send every permission request to Roundtable (`config.rs:150-162`; audit B26). The quoted basis "auto inside the workspace" (`config.rs:146`) appears in no owner document (audit §5). | PARTIAL (no GUI for scope; safety: audit B26, B28) |
| I-2 | Chair can hold, resume and give guidance | Hold and resume (`engine.rs:762-769`), guidance (`engine.rs:770-773`), page buttons (`index.html:115-118`). Guidance goes to every agent unjudged and enters JEV's window (audit B20). No test. | DONE |
| I-3 | `advance` tool, not role-restricted, normally used by the head | `mcp.rs:66-76`; applied only when the floor is free (`engine.rs:453-461`). Without JEV the tool says so. During a poll the tool still replies "Requested" while the engine refuses and tells only the chair (`engine.rs:785-786`; audit B3). Deferral awaits the owner (L K#13). Test: `advance_is_refused_truthfully_without_jev` (no-JEV case only). | PARTIAL (audit B2, B3) |
| I-4 | `feedback` tool: agents rate each other toward accolades and identity | `mcp.rs:21-37`, `engine.rs:791-806`. Feedback must name exactly one other participant (round 2 F11). It is saved to the identity file and `accolades.jsonl` (`web/app.rs:451-461`). Its keys are lowercase, not the owner's category names (audit D2). Accolades do not exist (audit M5). Whether the tool stays is open (N). | OWNER DECISION PENDING (audit B2, B4, D2, Q12) |
| I-5 | Reusable ACP system (autoselection, event bus, AgentSight) usable by the chassis; Roundtable standalone | `bus`, `acp-host`, `agent-monitor`, the `roundtable` library and the `roundtable-web` binary are separate crates. Use by the chassis is not shown in this repository. AgentSight needs root (H2). | PARTIAL |
| I-6 | No extra logic or gates | The mode gate and feedback category validation are gone. Gates that remain: `advance` refused during a poll or without JEV (audit B3), the next turn waits for JEV (audit B21), ratings and feedback refused for a name that matches more than one participant (`turn.rs:374-377`, `engine.rs:795-800`). The audit lists 38 builder additions (audit §4). | DIFFERS (audit §4; P5) |

## J. Proof points (D §10)

| # | Proof point | Status | Evidence |
|---|---|---|---|
| 1 | Trace shows the resolved ACP executable, `initialize`, `session/new`, `session/prompt`, real updates and completion | DONE | Records of live run `t72d45e26d24a` (N) and round 3 (O); acp-host tests. |
| 2 | `set_config_option` with the correct version-specific shape; OpenRouter model ids from the API with a separately identified runtime | DONE | `only_advertised_options_are_set` (v1 and v2). Model ids from `/api/models` (G6); the runtime (OpenCode or the SDK adapter) is a separate field (G9). |
| 3 | An occupied participant stays active while another takes its turn; the +512 skip credit and its return are visible; nothing cancelled | DIFFERS | The table moves on and nothing is cancelled (`tool_activity_marks_an_agent_working_and_the_table_moves_on`). A skip earns credit only when something new was accepted (audit D3). |
| 4 | Truncation before JEV; veto reasons and truncation counts on the next turn; no credit for a veto | PARTIAL | `a_vetoed_truncated_agent_gets_the_owners_format_at_its_next_turn`. The veto wording differs (audit D5). The notice can arrive in a non-discussion prompt (audit D7). |
| 5 | Two-round topic transition, proposals, pairwise judgments credited to both, summed, maximum chosen, two ties joined with "and" | PARTIAL | `topics_need_jev_and_follow_the_selection_rules` (fake JEV); live topic change (N). Only free participants propose (audit D4). |
| 6 | The next topic continues the same collaboration and workspace | DONE | D1. |
| 7 | AgentSight observations correlated to the ACP process or session | PARTIAL | Correlated by pid and harness id (H3). Observes nothing without root (audit D15). |

## K. Inventions awaiting the owner's keep or strike

Not called for by the spec or any owner decision. Status here says whether the section L or M verdict is in the code: DONE (verdict applied), REMOVED (struck and absent), PARTIAL, DIFFERS, or OWNER DECISION PENDING (L, M or N left it to the owner).

| # | Invention (as recorded) | Status | Code now |
|---|---|---|---|
| 1 | The exact `PASS` / first-line `WORK` reply convention (A4/A5). Reading the reply is necessary; only the exact matching rules are mine. | REMOVED (`WORK`); PASS reading kept per L | `WORK` is an ordinary contribution. PASS matches any case with trailing dots (`rules.rs:78-86`), while agents are told "exactly PASS" (audit B14). |
| 2 | The reply is the last text block after the final tool call (I10, copied from the archive). | KEPT, against the builder's L#2 STRIKE, because of an observed failure | Round 3 (`teb1471cdaf8a`): whole-turn transcripts were submitted as messages, giving 33 vetoes against 30 acceptances and one 73,807-character submission. The engine now submits `final_message`, the last non-empty block (`acp-host/harness.rs`, `engine.rs` `on_completed`). Risk: a real message followed by a tool call and a short closing line loses the message. |
| 3 | The allowance carries across topics (D3). | DONE | No reset rule (`turn.rs:315-333`), per L K#3. |
| 4 | A veto keeps the bank (A10 says only "no credit"). | DONE | A veto changes nothing beyond no credit (`turn.rs:163-181`), per L K#4. |
| 5 | Three-or-more ties are joined; with JEV off, every proposal is joined (C9). | OWNER DECISION PENDING (audit Q13) | The JEV-off case is gone: topics require JEV (M). Three or more ties still all join (`rules.rs:162-168`). |
| 6 | Proposals limited to 512 characters and called "private" (C10). | DONE | 512 kept (`rules.rs:12`); "private" gone (`prompts.rs:64-66`), per L K#6. |
| 7 | JEV sees only the current topic, capped at 24,000 characters (B5). | REMOVED | Replaced by the 50 KB rolling window from O:307 (`jev.rs:40-72`). See B5. |
| 8 | An "untrusted text" suffix on JEV questions (B9). | REMOVED | Gone from `jev.rs`. |
| 9 | Canned veto wording (B4). | DIFFERS (audit D5) | The notice quotes the owner's check question with JEV's confidence, per L K#9, inside a builder sentence (`prompts.rs:53-57`). The owner's earlier notices give no scores. |
| 10 | A warning after two idle topics (I4). | DONE | Kept as information only (`turn.rs:316-325`; audit B12), per L K#10. |
| 11 | A failed `mode` setting keeps the seat out (V8). | REMOVED | A failed setting is a loud error and the seat joins (`engine.rs:887-890`, `engine.rs:727-729`). |
| 12 | Feedback validation and categories (I6). | DIFFERS (audit D2) | Category validation is gone. The categories use lowercase keys (`rules.rs:180-181`, `mcp.rs:28-31`), not the owner's names and shape. Round 2 F11 added a check that feedback names exactly one other participant. |
| 13 | `advance` deferred until the floor is free; refused during a poll (I5). | OWNER DECISION PENDING (L K#13) | Deferral and poll refusal are still in the code (`engine.rs:453-461, 782-790`). The tool reply is truthful without JEV, not during a poll (I-3). |
| 14 | The floor is held while JEV judges a contribution (I15). | KEPT, against the builder's L#14 STRIKE | The owner's example in M needs the agent to see every other agent's message at its next turn, which requires the judgment to finish first. R §4.5 "the discussion continues normally" means no retry, then the next participant. Code: `engine.rs` `judging_floor`, `turn.rs` `submit`. Test: `a_vetoed_truncated_agent_gets_the_owners_format_at_its_next_turn`. |
| 15 | An empty reply counts as a failed turn (I11). | DONE | Loud error, no credit (`rules.rs:78-86`, `turn.rs:77-82`), per L K#15. Test: rules `replies_are_pass_contribution_or_empty`. |
| 16 | The first topic defaults to the objective; `R{topic}-{n}` message ids. | OWNER DECISION PENDING (first topic, audit B18); ids DONE | The first topic defaults to the objective (`engine.rs:267`). `R{t}-{n}` ids kept (`turn.rs:187-188`; audit B19). |
| 17 | Security hardening: secrets stripped from agents, the registry env deny-list, seat-name rules, the chair token. | OWNER DECISION PENDING (audit B29-B32; safety) | All still in the code (`config.rs:28-75`, `acp-host/launch.rs:173-177`, `web/app.rs:153-191`). |
| 18 | The hard-coded critics preset in the GUI. | REMOVED | Not in `index.html`. |
| 19 | Shutdown: SIGTERM, 3 s, SIGKILL (I1). This is your open question; the ACP SDK's own sequence is close input, 1 s, SIGTERM, 2 s, SIGKILL. | OWNER DECISION PENDING (audit D14) | The SDK sequence is in the code, marked "PENDING OWNER CONFIRMATION" (`acp-host/process.rs:20-27`). |

## L. Owner rule on additions and verdicts (2026-11-05)

Owner: "No invented behavior unless it addresses an observed failure... there is a reason for the behavior I put forth."

**Who wrote the verdicts (corrected 2026-11-05):** the rule above is the owner's. The KEEP and STRIKE verdicts in this table are the builder's, applying that rule. They are not owner rulings, and the owner's own words in M take precedence where they differ.

| K# | Verdict | Evidence or reason |
|---|---|---|
| 1 | Reading `PASS` from the reply: KEEP (parsing). `WORK` marker: STRIKE. An agent is occupied when ACP reports it working (tool activity), per D §6 and R §10 | no observed failure behind the marker |
| 2 | STRIKE: the reply is the agent's whole message | copied from the archive |
| 3, 4 | No rule added: nothing resets the allowance between topics; a veto changes nothing beyond "no credit" | absence of a rule |
| 5 | ASK THE OWNER: topic selection without JEV; three or more ties | something must happen; no observed failure |
| 6 | KEEP the 512-character limit on proposals (correction): the winning proposal becomes the topic text sent to every agent, so its cost is multiplied by the number of seats (R §1.2). STRIKE the "private" label | owner: "chats are amplified in cost by the number of participants" |
| 7 | STRIKE: JEV gets the whole accepted discussion; a JEV error is shown loudly and the contribution goes out unjudged | — |
| 8 | STRIKE | — |
| 9 | STRIKE the paraphrase: quote the spec's condition wording with JEV's confidence | — |
| 10 | KEEP (information only) | smoke test: ~1,590 topic cycles with every agent passing |
| 11 | STRIKE the gate: a failed setting is a loud error and the seat joins | — |
| 12 | STRIKE the validation; keep the owner's rating categories | categories come from the owner's earlier system |
| 13 | Bug fix: the tool's reply must tell the truth. ASK THE OWNER about deferring `advance` until the floor is free | the deferral fixed a failure the critics found by reading the code, not one observed in a run |
| 14 | STRIKE: the table continues while JEV evaluates (R §4) | — |
| 15 | KEEP, as a loud error with no credit | run 1: 44 empty replies (audit P06) |
| 16 | First topic: ASK THE OWNER. `R{t}-{n}` ids: KEEP | run 1: turn labels drifted, 15 mismatches (audit D01) |
| 17 | ASK THE OWNER (security-relevant) | critics' findings W1/S1 and others, from reading the code |
| 18 | STRIKE | — |
| 19 | KEEP process-group shutdown, using the ACP SDK's sequence (close input, 1 s, SIGTERM, 2 s, SIGKILL), pending the owner's answer | observed: agent processes outlived End in a live run |

## M. Owner answers (2026-11-05)

- **Topics require JEV.** "without jev the topic mechanism is moot.. topics require jev, the agents work towards the goal of the opening prompt." With judging off or JEV unavailable there is no topic progression and no next-topic poll; the agents work toward the opening prompt's objective. This replaces K#5 (unjudged pairs scoring 0 and every proposal joined). The three-or-more tie question applies only when JEV is present.
- **Crashes.** A crashed agent is a bug: fail loudly (a recorded, visible error), then fix it. No silent dropping and no hidden recovery.
- **Timers.** None anywhere: no deliberation window, no setup timeouts, no JEV time limit ("it gets a reply or an error").
- **Skips.** Being skipped while working counts as passing for the two-round rule.
- **Waiting.** If everyone is busy, or only one participant is free, the table waits. The idle agent is told to review the materials.
- **Additions.** "No invented behavior unless it addresses an observed failure."
- **Broadcast cost.** "chats are amplified in cost by the number of participants" (R §1.2). Everything sent to every agent (topic text, chair guidance, "since your last turn" summaries) is checked against this. The 512-character proposal limit stays.
- **Allowance (replaces R §4.3-4.4 crediting as implemented).** "the user can change the limit not the agents"; "it extends when they are credited for missed chats"; "the agent gets a credit to give a longer response because they have more to respond to".
  - The base limit is a chair setting (default 512).
  - ~~Each accepted message from another agent adds +512…~~ WITHDRAWN: it could give two credits for one skip (owner: "Why would an agent get double credit for one skip"). Proposed, AWAITING THE OWNER: a skipped turn, or a pass, earns at most one +512, and only if something new was accepted since that agent's last turn.
  - A pass or a skip adds nothing by itself.
  - An accepted contribution resets the allowance to the base.
  - A veto leaves the bank unchanged.
  - Agents cannot raise their own limit by anything they do.
  - **OPEN:** the verbatim R §3 prompt still describes "+512 per pass / per skipped turn". The owner must decide whether to reword it.
- **"Saying work, thats not a thing."** Agents do not announce work. The `WORK` reply convention and the prompt text describing it are removed from the design (K#1 struck outright). An agent is working when it is doing work, as observed through ACP activity (D §6).
- **Turn prompt format (owner, authoritative).** "Agent1 speaks, get vetoed, agent2, 3, 4 all speak, when it comes back to agent 1 it is informed if its message was truncated 'Message went past your 512 Character Limit, 23 Characters Lost' reason for the veto, each agents message, you have 512 Characters to Respond."
  - Order:
    1. The truncation notice, worded exactly: "Message went past your {limit} Character Limit, {n} Characters Lost".
    2. The veto reason.
    3. Each other agent's message, in speaking order.
    4. "You have {allowance} Characters to Respond".
  - Turns are sequential.
  - A vetoed agent that was neither passing nor skipped earns no credit from the messages it reads at its next turn.
  - This defines A11b (replaces the order in `turn.rs`).
- **Agent names (owner doc `archaeology/rich/technical/agent_identity.md`).**
  - An agent is born with its genesis context, the first session a harness opens for it, and that session's id seeds its identity.
  - Name = 32-bit FNV-1a of the session id's UTF-8 bytes, XOR-folded to 16 bits; the high byte picks one of 256 adjectives and the low byte one of 256 nouns (`dispatch/resources/names/`); both capitalized and joined.
  - The same id gives the same name, so a resumed session keeps it.
  - Code now: **VIOLATED.** It uses the chair-typed seat label, which exposes the model and gives ratings and accolades no stable identity.
  - Fix: compute the name from the `session/new` id; peers, the record and feedback use it.
  - **OPEN:**
    - Is the chair label kept for the chair only?
    - Should models be hidden from peers? (That rule came from the old builder's documents, not the owner's.)
- **Model visibility (owner).** "Agents are not told each others models but the user is." Peers see agent names only; the chair sees each agent's harness and model. (Answers the open question under Agent names.)
- **Ratings at the end (owner).** "what about agent ratings at the end and saving the agents rating."
  - When a table ends: a rating round in which each agent rates every other agent in the owner's categories (Efficient, Alert & Aware, Thorough, Coordination, plus bonus). Ratings are private between agents and visible to the chair.
  - Ratings are saved to each agent's identity (genesis name) and accumulate across tables. This follows [OWNER INSTRUCTION] "this score will be added to your agents identity as part of your profile in future sessions as well as accolades and recognition".
  - Code now: **MISSING.** Only the `feedback` tool exists, saving to `accolades.jsonl` under the chair label.
  - **OPEN:**
    - How does a rating carry forward: (a) by resuming that agent's session in later tables (recommended; fits the identity rule) or (b) per model, as the old version did?
    - Does the `feedback` tool stay alongside the end-of-table round?

## N. Status after the rewrite (2026-11-05 evening)

**Note (2026-11-05, refresh):** sections A-K were refreshed in place on 2026-11-05, so they now carry the current status of every row. The evidence is the read-only audit `review/AUDIT-OWNER-DESIGN.md`, spot-checked in the code. Rows below marked "Corrected 2026-11-05" were wrong against the current code; the original claim is kept in the row.

**Verification:**
- 58 workspace tests pass and clippy is clean.
- Live run `t72d45e26d24a` used Claude Code (`sonnet`) and Codex (`gpt-6.1-sol`).

Rows that changed status:

| Row | Status now | Evidence |
|---|---|---|
| A5, A14, H1: working means ACP tool activity; the table moves on; the reply after the work is the message | DONE | engine test `tool_activity_marks_an_agent_working_and_the_table_moves_on` |
| A11b + owner turn format | Corrected 2026-11-05 (was DONE): the owner's four-item order is DONE; the added topic line, chair lines and "[R1-2]" prefix DIFFER (audit D6) | test `a_vetoed_truncated_agent_gets_the_owners_format_at_its_next_turn`; live: "[R1-2] SteelForce: … You have 512 Characters to Respond" |
| A13 sequential loop; each judgment completes before the next turn (owner example) | DONE. The JEV wait conflicts with L K#14 and is open (audit B21, Q6) | same test; live record |
| A15, A16: two free to discuss; a lone agent asked once to review | DONE | test `a_lone_free_agent_is_asked_to_review_once_while_the_other_works` |
| Allowance: the chair's base; at most one credit per pass or skip, only when something new | Corrected 2026-11-05 (was DONE): the rule is in the code, but it DIFFERS from TPL:15 and R §4.3-4.4, which promise credit for every pass and skip. The rule itself awaits the owner (M; audit D3, Q1; P1) | rules tests; live: GenuineSilver +512 after a new message, SteelForce no credit with nothing new |
| B5: JEV sees the whole discussion, no cap | Corrected 2026-11-05 (was DONE, "no cap"): JEV gets the topic and the newest 50 KB of discussion as a rolling window, per the owner's instruction in O:307 | `jev.rs:40-72`, `turn.rs:119-124`; unit test `the_discussion_window_keeps_the_most_recent_50_kb` |
| B6/B7: JEV optional, fails open loudly, no timer | DONE | test `a_jev_failure_shares_unjudged_and_says_so` |
| B9, I9: untrusted-text suffix | REMOVED | — |
| C/M: topics require JEV; pairwise sum; ties joined in seat order | DONE. Only free participants are polled, which DIFFERS from R §7 (audit D4; P2) | test `topics_need_jev_and_follow_the_selection_rules`; live topic change |
| D3: allowance carries across topics | No rule (nothing resets it) | — |
| E4: "use tools first" prompt line; the `WORK` convention | REMOVED | rules test (`WORK` is a contribution) |
| F1: ACP v2 with v1 fallback | DONE | acp-host tests; live: both harnesses on v2 |
| F2: authenticate | DONE | acp-host tests (fake auth) |
| F4: set_config only for advertised options | DONE | acp-host test |
| F6: session load/resume | DONE (API). Corrected 2026-11-05: Roundtable never calls it, so the row is PARTIAL (audit M4) | acp-host tests |
| F8: session/close, then the SDK shutdown sequence | DONE. The shutdown sequence awaits the owner's answer | acp-host tests; live: no leftover processes |
| F10: v2 state updates | Corrected 2026-11-05 (was DONE): PARTIAL. `AgentState` events are published, but the engine does not use them and the v2 `background` report is ignored (audit M10) | acp-host tests |
| G6: OpenRouter models from the catalog in the GUI | DONE | `index.html` uses `/api/models` for OpenRouter harnesses |
| G7: OpenRouter Agent SDK ACP adapter | DONE | `adapters/openrouter-acp`, 20 tests at the time (25 in round 3; mocked; no paid calls) |
| H2/H3: AgentSight | Corrected 2026-11-05 (was DONE): H3 DONE; H2 PARTIAL. Without root it observes nothing, and descendant TLS is not captured (audit D15, M9) | `crates/agent-monitor`; attached per harness pid; loud error when not root. Verified as root in Boat sandboxes (process, file, network, HTTP). Locally unprivileged: refuses `sudo -n` |
| H7: crash fails loudly | DONE | test `a_crash_is_loud_and_the_table_ends_when_nobody_is_left` |
| Agent names: genesis rule | DONE. Profiles are keyed by display name, not by genesis session id (audit D11) | `names.rs` matches the owner's reference implementation (DeadeyeQuokka); live: GenuineSilver, SteelForce |
| Models hidden from peers, shown to the chair | DONE. Agents are not asked to keep their own model undisclosed (audit M7, open) | prompts list names only; the chair UI shows harness and model |
| Ratings at the end, saved to identity | Corrected 2026-11-05 (was DONE): PARTIAL. The rating round runs and saves points per name. The request text and category keys differ from the owner's (audit D1, D2). Results, receipt and the profile in later sessions are MISSING (audit M1-M3). Ratings do not accumulate across tables, because each table gets new genesis names (audit M4). A null or non-object peer card is dropped without a notice (`turn.rs:372-373`; round 3 N01, unfixed) | test `agents_get_genesis_names_and_rate_each_other_at_the_end`; live: 82 and 94 points; `~/.roundtable/identities/*.json` |
| I5: advance refused during a poll while the tool said "set" | Corrected 2026-11-05 (was FIXED): PARTIAL. The reply is truthful without JEV. During a poll the tool still replies "Requested" while the engine refuses and tells only the chair (`mcp.rs:71-75`, `engine.rs:785-786`; audit B3) | test `advance_is_refused_truthfully_without_jev` (no-JEV case only) |
| I6: feedback validation | REMOVED (owner categories kept). Round 2 F11 later added a check that feedback names exactly one other participant | — |
| V8: mode gate | REMOVED: a failed setting is a loud error and the seat joins | `engine.rs` `start_seat` |
| I14: critics preset; fixed model hints | REMOVED | `index.html` |

**Still open with the owner:**
- Credit rule wording confirmation. (O later marked the wording settled by the template. Corrected 2026-11-05: the code does not honor the template's promise, so the rule is open again; see P1.)
- Rewording the R §3 sentence about +512 per pass and per skip.
- Rating carry-forward: (a) by resume or (b) per model. Profiles are saved per genesis name today.
- Whether the `feedback` tool stays.
- Context handoff.
- TASTE.
- Three or more tied topics.
- Keeping the security hardening.
- `advance` deferral.
- The shutdown sequence.
- `session/close` waits for the agent's answer with no timer.
- AgentSight needs root (no `sudo -n`).
- The OpenRouter SDK bug to report upstream.
- The OpenRouter adapter does not accept MCP servers, so OpenRouter agents have no Roundtable tools.

## O. Owner decisions after round 2 (2026-11-05, late)

- **Participant prompt.** The owner supplied a new template that supersedes the R §3 wording ("I changed the wording a little bit more"). It is kept verbatim in `crates/roundtable/resources/participant_prompt.md`. `{{roundtable_prompt}}` takes the user's objective and `{{char_max}}` the table's base allowance. It settles the credit wording ("you will be credited back by adding the character count on your next reply") and the head-of-table suggestion, so those are no longer open in N. The builder's mechanics block now carries only what the template does not say: names and turn order, PASS, working, topics, and the tools for seats that have them.
- **Prompt visibility.** The owner could not see what agents receive ("I don't see it in startup unless its hidden"). The page now shows each seat's exact prompts.
- **OpenRouter models run on OpenCode.** "not ori .. we said opencode". `opencode acp` speaks ACP, accepts Roundtable's HTTP MCP tools, and runs OpenRouter models, the stealth ones included (verified live with stealth/crouton-alpha). Pi was considered and not used: pi-acp stores MCP servers but never wires them to Pi, so Pi seats would have no tools. Catalog OpenCode seats get a permission config that sends every request to Roundtable's workspace policy.
- **Round 3 seats.** Sol (Codex) plus Crouton, DeepSeek V4.1 Flash 1017, Hy4 and Mercury 3 on OpenCode. Sonnet dropped ("drop sonnet").
- **No longer open from N:** the credit wording (settled by the template). The repository adapter still has no MCP, but OpenRouter seats no longer depend on it.
- **JEV input, in the owner's words (2026-11-05):** "jef needs to be fed the topic and the past 50KB of the converesation as a rolling window". Implemented as `subject` (topic) and `recent_responses` (the last 50 KB), plus `candidate` and `objective`.
- **JEV checks:** the owner's three checks in `archaeology/roundtable-jev-checks.md` are used word for word ("I thought I provided the 3 prompts").

## P. Open owner decisions (2026-11-05)

Conflicts the owner must settle. Each line states the choice only; the audit's recommendations stay in the audit.

| # | Decision | Where |
|---|---|---|
| P1 | Credit rule: credit every pass and skip, as TPL:15 and R §4.3-4.4 say, or one credit only when something new was accepted (M, "AWAITING THE OWNER"). | audit D3, Q1; rows A4, A6, J3 |
| P2 | Topic poll: ask all participants (R §7, R §12, D §2 item 11) or free participants only (code). | audit D4, Q3; row C4 |
| P3 | Proposal comparison: same underlying intent with summed scores (R §7.1, R §7.3), or similarity with averaged scores (`archaeology/roundtable-jev-checks.md`, RT-007). | audit Q2, B8; rows C5, C7 |
| P4 | Which archaeology files are spec: the audit treats files marked (P) as provisional authority until the owner confirms them. | audit §1 "Sources" |
| P5 | The 38 builder additions: keep or strike each. | audit §4, B1-B38; rows I-6, K |
| P6 | Git: the project directory is not a git repository. The audit does not raise this item; it came with the request for this refresh, which found no owner text on it. | the request for this refresh |
| P7 | The 500-line file limit: the source files over 500 lines are `acp-host/harness.rs` (1,319), `engine.rs` (897), `web/app.rs` (615) and `agent-monitor/capture.rs` (558). The audit does not raise this item; it came with the request for this refresh, which found no owner text on it. | the request for this refresh |

Other open items: audit §5 (Q4-Q15) and the open list in section N.

## Q. Changes on 2026-11-06 (from the audit)

| Item | Status | Evidence |
|---|---|---|
| Rating request is the owner's exact scoring prompt (`roundtable-agent-ratings.md`, "Exact roundtable scoring prompt") | DONE | `resources/session_scoring.md`; test `the_rating_request_is_the_owners_scoring_prompt` reads the owner's document |
| Owner's category names "Efficient", "Alert & Aware", "Thorough", "Coordination", weights 10/20/30/40, bonus +5 | DONE | `rules.rs` `RATING_CATEGORIES`; `tests/rules.rs` |
| `score_received`, `session_results` / `session_rank`, `session_profile` sent as the owner wrote them | DONE | `resources/*.md`; test `the_owners_scoring_messages_are_sent` |
| Ratings carry forward: a seat can resume an earlier identity's session ("a resumed session keeps its name", AgentIdentity) | DONE | `SeatConfig.resume_session`; profiles record each identity's session and harness; page offers past identities; tests `a_resumed_seat_keeps_its_identity`, `identity_contexts_are_recorded_for_resuming` |
| Round 3 N01: a malformed rating card is reported | DONE | test `a_malformed_rating_card_is_reported` |
| `advance` tells the truth during a topic poll (L#13) | DONE | test `advance_is_refused_truthfully_during_a_poll` |
| K#14 JEV wait kept (owner's M example) | DONE | see K#14 row |
| Topic poll asks every agent (R §7): free ones at once, busy ones when free; the poll waits | DONE | tests `a_proposer_that_works_is_waited_for`, `an_agent_busy_at_poll_time_is_asked_when_free` |
| Audit D7, R §4.6: truncation and veto notices go only to the next discussion turn (floor or review), not to a proposal or rating request | DONE | `turn_prompt(.., discussion)`; test `a_veto_notice_waits_for_the_next_discussion_turn` (fails without the change) |
| Audit B1: the mechanics block says only what the code does. "exactly PASS" is now "reply PASS" (any case is read). The accolades claim is removed (none exist). The topic-end paraphrase is removed. "Free participants propose" is now "every participant" (agent text and MCP tool text) | DONE | `prompts.rs` `process`; `mcp.rs` |
| Audit: code comments that quoted the owner with words found in no owner text or session | DONE | Two quotes are real and now carry date and exact words ("fail loudly", "50KB"). "Back to 512", "the reply when the agent finishes…" and "auto inside the workspace" are relabelled as builder text. The timer comment now quotes the owner's actual words |
| Audit D11: profiles keyed by the identity's session, not its genesis name; names can collide (65,536 names) | DONE | `app.rs` `profile_path`, `update_profile`; events carry `to_session`; test `identities_with_the_same_name_keep_separate_profiles`. The 9 existing profiles were moved to session-keyed files; the originals are kept in `~/.roundtable/identities-by-name/` |
| Audit D12: an identity is unscored until its first rating | DONE (observable) | ranking shows "unscored"; the page selector shows "unscored" |
| Audit D13: scorecard validation | NOT DONE | the source is the old code's behaviour (`stages.py`), not owner design text |
| Audit D16, D §7.1: registry agents start through `acpr` when it is installed; without it, npx/uvx start directly and the catalog note says so | DONE | `launch.rs` `parse_registry_with`; test `registry_entries_resolve_npx_uvx_and_binary`. `acpr` is not installed on this machine |
| Audit M10, D §5.2: background work reported by an ACP v2 agent after its turn counts as working; its turns are skipped until it reports none | DONE | `AgentState.background`; engine `free_to_speak`; event `roundtable.background`; test `reported_background_work_skips_the_agent_until_it_ends` (fails without the change) |
| Owner's scoring rubric (category table and Bonus line, `archaeology/src/metaform/modules/tasks/resources/project_agent.txt:19-26`) added to the scoring prompt, unchanged; the build had left it out (audit Q7) | DONE (by the topogee session, verified here) | `resources/session_scoring.md`; test `the_rating_request_is_the_owners_scoring_prompt` |
