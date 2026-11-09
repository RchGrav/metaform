# ExaltedVesta — line-level verification evidence for the peer-rating findings

This file records *what I checked* so the decisions in `resolution.md` are auditable.

## Scope of the code available here

Files copied into `source/` that I read in full:
- `crates/roundtable/src/turn.rs`, `crates/roundtable/src/rules.rs`
- `crates/roundtable-web/src/app.rs`
- `resources/session_scoring.md`, `session_results.md`, `session_rank.md`,
  `score_received.md`, `session_profile.md`, `roundtable_prompt.md`, `participant_prompt.md`

Files the findings cite that are **NOT** in this folder (so their line numbers cannot be
checked here, only taken on the reviewers' report): `engine.rs`, `config.rs`, `tables.rs`,
`prompts.rs`, `docs/owner-sources/roundtable-agent-ratings.md`. Any decision that depends
only on those citations is marked "reported, not independently verified". No decision rests
solely on them: each finding has at least one checkable anchor in turn.rs / rules.rs / app.rs
or in `element.md` itself.

## Verified anchors

### Scoring formula (rules.rs:150-162)
```
RATING_CATEGORIES = [(Efficient,10),(Alert & Aware,20),(Thorough,30),(Coordination,40)]
stars = sum over keys of (value.as_f64().unwrap_or(0.0).clamp(0.0,5.0) / 5.0 * weight)
bonus = 5.0 if ratings["bonus"].as_bool()==true else 0.0
points = stars + bonus
```
- Missing key or non-numeric value -> `unwrap_or(0.0)` -> contributes 0. Verified at rules.rs:158.
- Max = 10+20+30+40+5 = 105, matching the doc comment "At most 105 points per rating" (150-151).
- So GF2's formula claim is correct, and the weights are *maximum points per category*, not
  percentages. This is exactly what GF7 says the description fails to state.

### Ranking (turn.rs:516-544)
- `rows.push((points, line))`; `rows.sort_by(|a,b| b.0.partial_cmp(&a.0))` — sorts by
  **summed session points**, descending (541-542).
- `rating`: `(None, 0) => "unscored"`, else `points(prior.score + points)` (529-533).
- `SESSION_RESULTS` wraps the joined rank lines (544).
- Verifies GF2's ranking claim.

### Saving is in the web host, not the core (app.rs)
- turn.rs:471-484 only does `session_points.entry(...).0 += points; .1 += 1` and
  `self.bus.publish(RatingGiven { ... })`. No file I/O, no profile write in the core crate.
- app.rs:98-102: on `envelope.name == "roundtable.rating"` call `save_rating(&identities, data)`;
  failure is published as a loud notice.
- app.rs:60-62: `data_dir = $ROUNDTABLE_HOME` or `$HOME/.roundtable`; app.rs:70: `identities` subdir.
- app.rs:430-443 `profile_path`: `<dir>/<session>.json` (session bytes escaped).
- app.rs:498-509 `save_rating` -> `update_profile`: `points += data["points"]` and appends a
  ratings entry. app.rs:450-475 `update_profile` writes atomically (tmp + rename).
- app.rs:478-496 `FileIdentities` implements the core's `Identities` trait — this is how the
  core *reads* profiles (turn.rs:39-40, 521) but the core never writes them.
- Verifies GF3 and GF8's storage/persistence claims. The "only tables.rs passes a store /
  spawn passes None" sub-claim (tables.rs:151, engine.rs:255, config.rs:42-50) is reported but
  not verifiable here.

### Failure modes (turn.rs:447-503)
- 450: `reply.find('{').zip(reply.rfind('}'))` -> slice `[a..=b]`, `serde_json::from_str(...).ok()`.
  Extraction is from the first `{` to the last `}`; a parse failure yields `None`.
- 453-461: `json.as_ref().and_then(|v| v.as_object())`; a non-object top level -> `None` branch
  (487-491) which clears `unrated` and records nothing, with one error notice. A card whose
  value is not an object -> `continue` with a per-card error notice (456-461).
- 463-467: `targets` = seats (j != i) whose `name == to_name`; `if targets.len() != 1` -> reject.
  Zero matches (unknown name) and several matches (duplicate names) both drop the card.
- Duplicate-name consequence is subtler than GF4 states (refined after a roundtable
  qualification): turn.rs:438/452 build `others`/`unrated` by filtering on the rater's own name,
  so two same-named seats are never *asked* to rate each other; a third rater's card for that
  name is rejected (targets.len()==2, 463-467). BUT a manually supplied card from one of the two
  same-named seats to the other matches exactly one target, because 463 excludes the rater
  (`j != i`) — so that card IS recorded. GF4's blanket "cannot rate each other" is therefore
  imprecise. Verified.
- 493-497: missing ratings produce one error notice; there is no re-prompt (the rater is not
  asked again). Verified.
- Verifies GF4 fully.

### Messages (turn.rs)
- 498-501: `SCORE_RECEIVED` offered as `Activity::Notified` when the JSON was a readable object.
- 37-50: on `seat.first`, a returning identity with `profile.ratings > 0` gets `SESSION_PROFILE`
  ("Your profile score is ... You have N ratings across M earlier sessions").
- 551-560 `settle_results`: sends only to `state==Ready && name.is_some() && activity==Idle &&
  !results_sent`.
- 564-575 `check_results_done`: ends the table (`end("ended by the chair")`) once no seat is
  still waiting.
- Verifies GF5.

### `element.md` itself (comprehension findings)
- rules[0] = "When a table ends, each agent rates every other in the owner's categories
  (Efficient 10, Alert & Aware 20, Thorough 30, Coordination 40, bonus +5) using the owner's
  scoring prompt." — no legend for the numbers, no definition of "table", no trigger, no
  mention of chair/evaluator, no qualification of which seats participate.
- rules[1] = "Each agent then receives the owner's results message; ratings are saved to each
  agent's identity." — "identity" undefined, no storage location, "results" undefined.
- wants: `code.manager.chat.group` "Collects every agent's ratings of the others and returns
  the results" (Intent: send_receive) — vs rules[1] "receives the owner's results message".
- references: two bare paths, no annotation; "owner" never introduced; owner_statements[0] is
  the question "what about agent ratings at the end and saving the agents rating" with no link
  to the categories/weights.
- elephant.gaps: "Ratings carry to a later table only if that table resumes the agent's earlier
  session." Confirms the persistence condition GF8 cites.
- These directly substantiate GF7, GF8, GF9, GF10, GF11, GF12 as *documentation* gaps.

## GF6 — initial "NOT right", RECLASSIFIED to "partially right" after a roundtable challenge

GF6 says `session_scoring.md:3-10` "adds the worker rubric table, which the owner's roundtable
prompt does not contain (docs/owner-sources/roundtable-agent-ratings.md:57-61, 113)", implying a
discrepancy behind rules[0]'s "owner's scoring prompt".

My first reading compared `session_scoring.md` to `roundtable_prompt.md` (the general discussion
prompt) and judged the finding a conflation: the rubric belongs in the scoring prompt, the
general prompt rightly omits it, so no defect. **That rebuttal was aimed at the wrong comparison.**
StalkyValor (`StalkyValor-verdict.md`) and DeifiedArrow (appended qualifications) pointed out the
parenthetical cites the *owner's original source document*, not the prompt template. Read as a
provenance/attribution nit — is the rubric/bonus/JSON contract actually owner-specified, or
implementation-added? — the label "owner's scoring prompt" is genuinely imprecise. A flat "not
right" was too strong.

Verifiable in-folder: `session_scoring.md:3-13` has the rubric table, bonus criterion, and JSON
instruction; `rules[0]` labels it "the owner's scoring prompt"; `references` leaves it unlabeled.
Not verifiable in-folder: whether `roundtable-agent-ratings.md` lacks the rubric, and whether
`prompts.rs:92-93` includes the resource verbatim (both files absent). So GF6's central factual
premise can be neither confirmed nor refuted here — this is exactly the verification caveat.

**Reclassified verdict: partially right.** Legitimate documentation/attribution nit; fix is to
label `session_scoring.md` as a *composite resource* (owner notice + rubric + bonus + JSON
format), merge with GF11's reference annotation, keep the rubric, and require inspecting the
owner source before claiming verbatim ownership. No code change. The `resolution.md` GF6 section
records this verdict evolution explicitly for auditability.

## Overlap map (so the fixes are not duplicated)

- Scoring notation + formula + ranking: GF7 (scale/legend/basics) + GF2 (formula, silent zeros,
  ranking) -> one expanded rules[0] plus a "results" definition.
- Saving + identity + persistence + storage: GF3 (who saves, where) + GF8 (define identity,
  link code.identity.agent, persistence condition) -> one "identity & storage" section.
- Triggers + participants: GF1 (when the round runs/skips, which seats) + GF10 (define table,
  end triggers, chair/evaluator scope, departed/non-answering) -> one "scope & triggers" section.
- Robustness + messages: GF4 (failure modes) + GF5 (receipts/profile line/results delivery).
- Terminology: GF6 (not right) + GF11 (label references, introduce owner) + GF12 (provenance of
  categories).
