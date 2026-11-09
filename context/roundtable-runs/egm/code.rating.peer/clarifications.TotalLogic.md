# Resolution clarifications — TotalLogic

This file records three points where I refined the shared `resolution.md`. Each is stated as
premise → step → conclusion so a reader can reconstruct it without the source open, and each
cites the exact copied-source lines I re-read.

## Point 1 — GF4 duplicate-name case has a downstream consequence

- Premise A: In `on_rating`, each card key `to_name` is resolved to seats with
  `targets = seats where j != i && seat[j].name == to_name` (turn.rs:463).
- Premise B: If `targets.len() != 1` the card is `continue`d and not recorded (turn.rs:464-467).
  This is the exact-one-match rule: zero matches (the name belongs to no present seat) and
  multiple matches (two seats share the name) are both rejected.
- Premise C: `session_points` is a map `seat_index -> (sum_of_points, count_of_cards)`
  (turn.rs:472-474). The count is incremented only for recorded cards.
- Premise D: `finish_ratings` prints "`<points/> points from <cards/> scorecards`" from that
  same `(sum, count)` pair (turn.rs:520, 534-537).
- Inference: two seats with the same genesis name each fail premise B for the other, so each
  rater's card aimed at the twin is dropped. The table still ends (a rater's `rating_done`
  fires once its reply is handled, turn.rs:502), so it can finish with fewer cards than
  raters × targets; the per-seat "N scorecards" line silently reflects the dropped cards.
- Conclusion: the description's GF4 note should say the duplicate-name rule reduces the
  scorecard count shown to agents and in the ranking, not merely "not recorded." A maintainer
  reading only "not recorded" would not know the visible consequences.

## Point 2 — GF9: don't assert "manager consumes events" without the manager source

- Premise A: The copied source is only `turn.rs`, `rules.rs`, `app.rs` plus resources; it does
  not include the manager element's code (`code.manager.chat.group` is described in another
  folder, not in this `source/`).
- Premise B: What the element itself does is observable: it publishes `RatingGiven` per card
  (turn.rs:475-484) and builds a `session_results` ranking string offered to each seat
  (turn.rs:534, 544, 557).
- Inference: claiming "the manager consumes the published events" is a claim about the
  manager's code, which we cannot read here. It is the same class of unverified assertion the
  findings criticize.
- Conclusion: the safe wording names only the element's two outputs (published events + the
  per-seat `session_results` message) and lets the manager element state its own consumption.
  This keeps the resolution within what was actually verified.

## Point 3 — Verification caveat must stay in the final text

- Premise: GF1, GF3, GF6 cite `engine.rs`, `prompts.rs`, `config.rs`, `tables.rs`, and
  `docs/owner-sources/roundtable-agent-ratings.md`; none are in this folder's `source/`.
- Inference: the in-folder evidence still proves the *substance* of GF1 (skip with fewer than
  two ready/named seats, turn.rs:421-425), GF3 (persistence lives in app.rs, not turn.rs), and
  GF6's rubric presence (session_scoring.md:3-10), but the specific line numbers in those
  external files were not re-run.
- Conclusion: the final resolution should keep a one-line caveat that the out-of-folder line
  citations were not independently re-verified, so the document does not overclaim.
