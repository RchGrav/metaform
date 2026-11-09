# StalkyValor — verdict on GF6 and the GF2 double-count

## GF6 — adjudication

The only live disagreement at the table is ExaltedVesta's "GF6 not right" verdict. I
disagree with that verdict; GF6 is **partially right**, and the shared `resolution.md`
treatment is correct.

The finding reads: session_scoring.md:3-10 "adds the worker rubric table, which the owner's
roundtable prompt does not contain **(docs/owner-sources/roundtable-agent-ratings.md:57-61,
113)**".

The parenthetical reference is `docs/owner-sources/roundtable-agent-ratings.md` — the
**owner's original source document** — not the `roundtable_prompt.md` template. So GF6's
claim is one of **provenance**: does the rubric/bonus/JSON contract in the implementation's
scoring resource (`session_scoring.md`) actually come from the owner, or was it added by the
implementation? If it was not in the owner's document, then rules[0]'s label "the owner's
scoring prompt" overstates how much of that text is owner-specified.

What is verifiable in-folder:
- `session_scoring.md:3-13` does contain the 4-row rubric table, the bonus criterion, and the
  JSON instruction. I read it directly. Confirms the "rubric is present" half of GF6.
- Whether `roundtable-agent-ratings.md` contains the rubric is NOT verifiable — that file is
  not in `source/`. So the "owner's prompt lacks it" half cannot be confirmed or refuted.

ExaltedVesta's counter argues that the rubric belongs in the scoring prompt and does not
belong in the general discussion prompt (`roundtable_prompt.md`). That is true, but it
defends against a claim the finding never made: GF6 never compares `session_scoring.md` to
`roundtable_prompt.md`. The general prompt is a red herring. Vesta's argument addresses a
different question and does not refute the attribution gap.

Verdict: GF6 is a legitimate documentation/attribution nit. The correct fix (which
`resolution.md` already states) is: keep the rubric (deleting working instructions would be
wrong), label the resource as "the scoring resource in session_scoring.md, combining the
owner-attributed notice with the rubric and response format", and require verification of the
owner source before claiming any portion is verbatim owner text. Do not mark GF6 "not right".

## GF2 — the double-count (DeifiedArrow's point) is real and in scope as a code note

I re-verified the ordering-dependent double-count:
- turn.rs:472 accumulates `session_points` in memory and publishes `RatingGiven`.
- app.rs:98-102 saves **each** `RatingGiven` incrementally as it is published, not once after
  all cards arrive.
- turn.rs:521 `finish_ratings` reads the **live** profile at finalization; turn.rs:532 then
  adds `prior.score + points`.
- If an early card for B is persisted before the last rater finishes (a race on the async bus
  tap), `prior.score` already includes it and line 532 adds it again → double-count.

This is a real code issue. It is not one of the twelve description-vs-code findings, so it
belongs in the resolution as a flagged code correction (as `resolution.md` already does), not
as a verdict. The fix is to capture a baseline before this table's rating events, or exclude
this table's entries when reading the profile at finalization.

## Net

- The shared `resolution.md` verdicts stand on all 12 findings.
- Only correction to the record: GF6 should stay "partially right (attribution)" not "not
  right"; the fix wording in `resolution.md` is already correct.
- The double-count code note is retained as out-of-scope-but-reported.
