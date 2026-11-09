# DirectOmega — verification ledger (GF1–GF12)

Companion to `resolution.md`. Line numbers refer to the files in `source/`.

## Source inventory
- `engine.rs` = 997 lines (matches reviewer citations).
- `rules.rs` = 175 lines (matches reviewer citations).
- Absent but cited by findings: `turn.rs`, `config.rs`, `jev.rs` (and `prompts.rs`,
  `events.rs` are referenced by engine.rs). Methods called-but-not-defined in engine.rs:
  `start_rating`, `resolve_reply`, `commit`, `turn_prompt`, `on_judged`, `on_rating`,
  `on_proposal`, `on_scored`, `change_topic`, `start_polling`, `finish_polling`,
  `settle_poll`, `settle_results`, `ask_to_rate`, `rating_done` → they live in `turn.rs`.
  So the provided source is a partial copy; claims resting only on absent files are
  accepted on consistency, not direct confirmation.

## Direct confirmations (present files)

| Ref | Code | Confirms |
|---|---|---|
| engine.rs:6-8 | "not asked to announce work (O: 'Saying work, thats not a thing')" | GF1 (no WORK token) |
| engine.rs:666-681 | `on_tool`: Floor→Working on `ToolActivity` | GF1 (work from ACP activity) |
| rules.rs:50-59 | `classify` = Empty / Pass / Contribution | GF1 (3 kinds only) |
| rules.rs:54 | `trim_end_matches('.').eq_ignore_ascii_case("pass")` | GF1 (PASS case/dots) |
| engine.rs:12 | "No timers anywhere (O)" | GF2, GF3, GF8 |
| engine.rs:396-399 | `limit_for`: `base_allowance?` short-circuits recovery | GF6 (quota) |
| engine.rs:510-513 | `step` returns while floor / judging_floor Some | GF3 (JEV wait), RT-G10 |
| engine.rs:541-552 | `free.len() < 2` → `waiting_for_free = true` | GF3, GF8 (RT-G03) |
| engine.rs:503-508 | poll returns until waiting/pending empty | GF3 (poll waits all) |
| engine.rs:636-640 | `cfg.rounds == Some(round_no)` → `start_rating` | GF4 (auto end) |
| engine.rs:647-651 | no-limit two-quiet-round end, gated on `!topics_active() \|\| !topic_had_input()` | GF4, GF5, GF9 |
| engine.rs:653-656 | `advance && topics_active()` → `topic_due` (poll) | GF5, GF9 (RT-G08) |
| engine.rs:168-170 | `ranking`, `session_points` fields | GF4 (session ranking) |
| rules.rs:102-110 | `close_round`: `n>=2 \|\| a>=2`; `passed` includes SkippedWorking (91) | GF5 (pass/skip rounds count) |
| engine.rs:499-500 | `seating` guard | GF6 (turns start after all seats) |
| engine.rs:789-792, 838-841 | "no participants left" / "no participant could start" → `end` | GF6 |
| engine.rs:901-907 | `Command::End` two-step | GF6 |
| engine.rs:543, 554-556, 586 | `told_to_review` guard / reset / set | GF6 (once per episode) |
| engine.rs:873-880 | `Advance` refused when `!topics_active()` or during poll | GF11 |
| engine.rs:374-379, 272 | `topics_active` = cfg.topics && judging && jev.configured() | GF4, GF7, GF11 |
| rules.rs:8,12,15,17,19 | DEFAULT_BASE 512, DEFAULT_ROUNDS 10, GATE_PASS .70, SCORE_PASS 3.0, PROPOSAL_LIMIT 512 | GF2, GF4, GF6 |

## Description-internal contradictions (no code needed to verify)
- `decisions` 72-84, 88-97 (11-05) vs `rules` 172-174, `gates` RT-G03/05/06/10,
  `elephant.built` 236, `owner_statements` 137-142 (11-07). → GF7.
- `owner_statements` line 113 ("nothing waits", "only pause is chair hold") vs `gates`
  RT-G03 / RT-G10 and `rules[1]`. → GF3, GF8.
- `wants` line 17 ("through the normal poll") vs topics-off-by-default. → GF11.
- `rules[0]` single-line ending vs `code.selector.topic` want line 30 / RT-G08. → GF9.
- Undefined terms throughout; opening line 3 says "an evaluator" but never names JEV. → GF10.
- `Properties` 7-13; `investigations` 150-152 stale; `elephant.gaps` 239 "500-line limit"
  has no source. → GF12.

## The single root cause
11-05 `decisions` + 11-05 owner consequence describe an abandoned design. 11-07 owner
direction ("10 rounds by default", "unlimited must have some kind of end") + the `rules`,
`gates`, `elephant.built` layers describe the current design, which the code implements.
engine.rs:7 quotes a newer owner decision ("Saying work, thats not a thing") and
engine.rs:12 records "No timers anywhere (O)". Therefore: **fix the description (mark stale
layers superseded, correct wording, add missing detail), do not change the code.** Adding
timers/bounds to "fix" GF3/GF8 would violate an explicit owner decision and RT-G03's
"owner-designed" status; the residual stall should be put to the owner instead.

## Verdicts
GF1 R, GF2 R, GF3 R, GF4 R, GF5 R, GF6 R, GF7 R, GF8 R, GF9 R, GF10 R, GF11 R, GF12 R.
All twelve right; all resolved by description edits; zero code changes.
