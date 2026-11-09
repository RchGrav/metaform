# SmokyBastion: verification notes for the accolades findings

Purpose: record what I could and could not verify from the copied `source/` tree, because
three of the ten findings cite code that is not present in this folder. The resolution must
distinguish "verified false against the code I have" from "unverifiable here".

## Files present

`source/crates/roundtable-web/src/app.rs`, `source/crates/roundtable/src/turn.rs`,
`source/docs/owner-sources/roundtable-agent-ratings.md`. Everything else the findings cite
(`mcp.rs`, `engine.rs`, `rules.rs`, `index.html`, `prompts.xml`, `stages.py`, `store.py`,
`runner.py`) is absent.

## Claims I confirmed in `app.rs`

- `app.rs:69` builds `accolades = data_dir.join("accolades.jsonl")` where `data_dir` is
  `ROUNDTABLE_HOME` or `~/.roundtable` (app.rs:54-58).
- Only `roundtable.feedback` is appended to that file (app.rs:103-111). The same event also
  calls `save_feedback` (app.rs:104) which, per its doc comment and unit test, adds no
  points ("feedback adds no points", app.rs:704).
- `roundtable.rating` triggers `save_rating` (app.rs:98-101) which *does* add
  `data["points"]` to `profile["points"]` (app.rs:500-508) and pushes to `profile["ratings"]`.
  It never touches `accolades.jsonl`.
- So: filesystem "accolades" = unweighted feedback; identity "points" = weighted ratings.
  The two paths are disjoint. This is exactly GF3's claim and it is right.
- Points are consumed only by `identities_list` sorting (app.rs:567) and by the identity
  profile read at `turn.rs:41-46` (the `SESSION_PROFILE` prompt). No code here weights,
  ranks or selects returners. GF4 is right that rating feeds ordering only.

## Claims I could not verify (source missing)

- GF1's `mcp.rs:22-36,84-104` (the `feedback` tool) and `engine.rs:882-898` (`FeedbackGiven`
  keyed by `to_session`): absent. However `app.rs:104` consumes a `roundtable.feedback`
  event carrying `to_session`, `to_name`, `from_name`, `ratings`, `note`, and `app.rs:416`
  treats `roundtable.feedback` as a real event. That is consistent with GF1's account.
  It also means `code.rating.peer` (element.md, elephant.built) is probably the wrong name;
  the peer tool is `feedback`.
- `index.html:416-417` (resume picker label): absent. Directionally consistent with
  `identities_list` returning `points` per identity for a picker.
- The archaeology paths (`prompts.xml`, `stages.py`, `store.py`, `runner.py`): absent
  from the repo, which is *why* GF2 and GF7 are right.

## Reproduction of the scale mismatch (GF8)

`docs/owner-sources/roundtable-agent-ratings.md` is the only in-repo source and it states
the weights concretely: Efficient 10, Alert & Aware 20, Thorough 30, Coordination 40,
`points = 10*E/5 + 20*A/5 + 30*T/5 + 40*C/5 + (5 if bonus)`, max 100 (105 with bonus).
The element description never states this, so GF8 is right that the scale is unreconciled.
