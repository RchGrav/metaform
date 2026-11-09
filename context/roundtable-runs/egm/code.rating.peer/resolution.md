# Resolution of review findings — `code.rating.peer` (peer rating round)

Decisions for GF1–GF12 in `element.md`. Each is judged against the code in `source/`.
Line references are to the copies in `source/crates/...`.

## Method and scope note

The reviewers cite `engine.rs`, `config.rs`, `tables.rs`, `prompts.rs` and
`docs/owner-sources/roundtable-agent-ratings.md`. **Those files are not in `source/`**, so their
specific line numbers could not be independently checked here. Every finding also has a checkable
anchor in `turn.rs`, `rules.rs`, `app.rs`, the `resources/*.md` files, or `element.md` itself, and
each verdict below rests on those verified anchors. Sub-claims that depend only on the absent
files are noted as "reported, not verified"; none of them change a verdict.

**Summary:** all twelve findings are **right or partially right** (all are description /
comprehension / attribution gaps; no code bug is found in the rating logic itself). GF1–GF5 and
GF7–GF12 are **right**; **GF6 is partially right** — reclassified after a roundtable challenge
showed it is a provenance/attribution nit, though its central factual premise is unverifiable
here (see the GF6 section). The fixes are entirely to `element.md` (the functional map), not to
the code, because the code is coherent and the reviewers' substantive observations are things the
description fails to say. Several findings overlap; a consolidated fix plan is given at the end
so the same edit is not made twice.

| Finding | Verdict | Kind of fix |
|---|---|---|
| GF1 | Right | description: qualify triggers and eligible seats |
| GF2 | Right | description: state scoring formula + ranking |
| GF3 | Right | description: name the host + storage; correct `elephant.built` |
| GF4 | Right | description: add failure modes |
| GF5 | Right | description: add receipts, profile line, results delivery |
| GF6 | **Partially right** (reclassified) | description: label `session_scoring.md` as a composite resource; provenance nit, premise unverifiable (merge with GF11) |
| GF7 | Right | description: add scorecard legend (merge with GF2) |
| GF8 | Right | description: define identity, link, persistence |
| GF9 | Right | description: define "results", manager vs agents |
| GF10 | Right | description: define table, end triggers, scope |
| GF11 | Right | description: annotate references, introduce "owner" |
| GF12 | Right | description: record provenance of categories |

---

## GF1 (Major) — trigger and participants — RIGHT

`rules[0]` says "When a table ends, each agent rates every other". This overstates the eligible
set and hides the conditions.

Verified anchors:
- `turn.rs:421-425` `start_rating`: the round is skipped entirely when fewer than two seats are
  `SeatState::Ready` **and** have a name (`left.len() < 2` -> `end("ended by the chair")`).
- `turn.rs:429-433`: only idle seats in that set are asked now; busy ones are asked later when
  free (`ask_to_rate` via `settle`-style logic), and `RatingsAsked` lists only those seats.
- `turn.rs:438, 452`: the rater is asked to rate `names() != me`, i.e. only other **named** seats.
- `turn.rs:493-497`: a missing rating produces one error notice and **no retry**.
- `turn.rs:723-724` (departed seats dropped) and the engine-level triggers (chair End at
  `engine.rs:906`, last round `engine.rs:636-639`, two quiet rounds `engine.rs:647-650`, skipped
  on a second End `engine.rs:903` and other ends `engine.rs:791, 840`) are **reported, not
  verified** here, but are consistent with `start_rating` being an `end`-time routine.

**What should change:** in `element.md`, qualify `rules[0]` to "each *ready, named* agent still at
the table rates the other ready, named agents", and add a layer (or bullet) recording: the round
runs only when the table ends under the normal endings, is skipped with fewer than two eligible
seats or on a forced/immediate end, departed seats are dropped, and a missing rating is reported
without a retry. Why: a reader of the map cannot otherwise tell who is rated or when the round is
bypassed. See also GF10 (define "table"/"ends").

## GF2 (Major) — categories, weights, scoring rule, ranking — RIGHT

All parts verified:
- `rules.rs:150-162` `rating_points`: each category contributes
  `value.clamp(0.0,5.0)/5.0*weight` with weights 10/20/30/40; missing or non-numeric values
  fall through `unwrap_or(0.0)` and silently count as 0 (`rules.rs:158`); `bonus` adds 5.0 only
  when a boolean `true` (`rules.rs:160`). Max = 105, matching the doc comment (`rules.rs:150-151`).
- `turn.rs:529-544`: `rating = prior_profile_score + session_points`, `"unscored"` when there is
  no prior profile and zero cards; `rows.sort_by` on summed session points (a sum, not an average).

The `rules[0]` line lists the numbers but states none of this. **What should change:** add the
scoring rule to the description — stars 0–5 per category scaled by weight/5, +5 for a true
bonus, per-card max 105, missing/non-numeric = 0 — and add that the results message is a ranking
by summed session points where each rating is the earlier profile score plus this session's
points, with "unscored" until rated. Why: this is the central computation of the element and is
currently unstated. Merge with GF7 (which asks for the same legend) into one rules[0] edit.

## GF3 (Major) — saving; `elephant.built` — RIGHT

Verified:
- `turn.rs:471-484`: the core only accumulates `session_points` and publishes the `RatingGiven`
  event (consumed as `roundtable.rating`). No disk write, no profile mutation in the core crate.
- `app.rs:98-102`: the web host taps `roundtable.rating` and calls `save_rating`; persistence
  errors are published as loud notices.
- `app.rs:60-62, 70`: storage root is `$ROUNDTABLE_HOME` (else `$HOME/.roundtable`), identities
  under `identities/`. `app.rs:430-443`: profile file is `<session>.json`.
- `app.rs:498-509` `save_rating` -> `app.rs:450-475` `update_profile` (atomic tmp+rename) adds
  points and appends the rating. `app.rs:478-496` `FileIdentities` is the core's read-only
  `Identities` implementation (used at `turn.rs:39-40, 521`).
- `elephant.built` says "turn.rs ... records each scorecard and sends the owner's results
  message" — it does not record scorecards to identities; the host does.

The sub-claims "only `tables.rs:151` passes an identity store" and "spawn passes `None`,
`engine.rs:255`", and "`config.rs:42-50` only reads profiles" are **reported, not verified**
(files absent), but the architectural point is confirmed by `app.rs`: saving lives in the web
host and is driven by an event, not by the core.

**What should change:** in `element.md`, `rules[1]`/`elephant.built` should say the core emits
`roundtable.rating` events and that the **web host** persists them to
`$ROUNDTABLE_HOME/identities/<session>.json` via `save_rating`; note that persistence therefore
depends on the host running and on an identity store being supplied to the table. Correct
`elephant.built` so it no longer credits `turn.rs` with saving. Name the host crate/path. Why: the
description currently attributes an action to the element that the element does not perform.

## GF4 (Major) — failure modes — RIGHT

All verified in `turn.rs:447-503`:
- `450`: JSON is taken from the first `{` to the last `}`; a parse failure yields `None`.
- `487-491`: unreadable/top-level-non-object JSON records nothing (one error notice).
- `456-461`: a card whose value is not an object is rejected with a per-card notice.
- `463-467`: a name matching zero or several other seats is not recorded.
- Duplicate-name consequence, stated precisely (refines the reviewer's wording). Three distinct
  effects follow from `438`, `452` and `463`:
  - The rating *request* (`others`, `438`) and the missing-rating check (`unrated`, `452`) are
    built by filtering on the rater's own name, so two seats sharing a name are never *asked* to
    rate each other.
  - A **third** rater's card keyed to that shared name matches both seats (`targets.len()==2`,
    `463-467`) and is rejected.
  - But a **manually supplied** card from one of the two same-named seats to the other resolves
    to exactly one target: `463` excludes the rater (`j != i`), so with exactly two "X" seats the
    card matches only the peer and **is recorded**. The reviewer's blanket claim that "two agents
    with the same name cannot rate each other" is therefore imprecise — the automatic prompt
    omits the peer, yet the parser permits a manual card between exactly two same-named seats.
    (Credit: raised as a qualification by another participant; verified against `turn.rs:463`.)

The finding is still right: the name-keyed matching is a real, undocumented limitation. The fix
should describe all three effects, not repeat the overstated one.

Downstream consequence (adopted from the roundtable, `clarifications.TotalLogic.md` Point 1):
`session_points` is `seat_index -> (sum, count)` and `count` rises only for recorded cards
(`turn.rs:472-474`); `finish_ratings` prints "`<points/> points from <cards/> scorecards`" from
that same pair (`turn.rs:520, 534-537`). Since each rater's reply is still handled and the table
still ends (`turn.rs:502`), dropped cards mean the table can end with **fewer cards than
raters × targets**, and the per-seat "N scorecards" line silently reflects the loss. This is the
visible effect a maintainer needs: it is a *functional limitation with a displayed consequence*,
not merely "not recorded". The description note must say so.

**What should change:** add a "failure modes / robustness" layer to `element.md` recording these
behaviours, including the precise duplicate-name semantics above and the fewer-cards-than-expected
effect on the ranking line. Why: they determine which scorecards actually count and are entirely
undocumented.

## GF5 (Major) — messages — RIGHT

Verified:
- `turn.rs:498-501`: a `score_received` receipt ("Your private scorecard was received.") is sent
  when the card was readable; `score_received.md` confirms the text.
- `turn.rs:37-50`: a returning identity with prior ratings gets the `session_profile` line on its
  first turn ("Your profile score is ... You have N ratings across M earlier sessions");
  `session_profile.md` confirms.
- `turn.rs:551-560`: results go only to seats still `Ready`, named, `Idle`, and not already sent.
- `turn.rs:564-575`: the table ends once all such seats are sent (`end("ended by the chair")`).
  Two verified refinements (raised at the table, `DeifiedArrow-notes.md` / appended qualifications):
  `check_results_done` (`turn.rs:568-570`) also waits while an eligible seat is in
  `Activity::Notified`, so "ends once all are sent" is incomplete — notification replies must
  settle too; and `results_sent` is set before `offer`, whose success is ignored (`556-557`), so
  the verified contract is *attempted* delivery, not guaranteed receipt.

`rules[1]` mentions only "receives the owner's results message". **What should change:** record
the `score_received` receipt, the first-turn `session_profile` line for returning identities, and
the delivery/end conditions. Why: `rules[1]` is otherwise an incomplete account of what agents
receive. Note the profile line is a first-turn identity feature, not strictly part of the rating
round; document it as a related behaviour rather than moving it into the round.

## GF6 (Nit) — "owner's scoring prompt" / rubric table — PARTIALLY RIGHT (reclassified)

**Verdict evolution (kept for auditability).** My initial independent verdict was "not right": I
read GF6 as comparing `session_scoring.md` to the general discussion prompt
(`roundtable_prompt.md`), and argued the rubric belongs in the scoring prompt, so no discrepancy
exists. On the roundtable, StalkyValor (`StalkyValor-verdict.md`) showed the finding's
parenthetical cites `docs/owner-sources/roundtable-agent-ratings.md` — the **owner's original
source record**, not the `roundtable_prompt.md` template. Read that way, GF6 is a **provenance /
attribution** nit: does the rubric, bonus criterion, and JSON contract in `session_scoring.md`
actually come from the owner, or was it added by the implementation? If not owner-specified,
`rules[0]`'s label "the owner's scoring prompt" overstates how much of that resource is
owner text. My earlier rebuttal defended against a different comparison than the finding made,
so a flat "not right" was too strong. Reclassified to **partially right**.

What is verifiable in-folder:
- `session_scoring.md:3-13` does contain the 4-row rubric table, the bonus criterion, and the
  JSON scorecard instruction. Confirms the "rubric is present" half.
- `rules[0]` calls this "the owner's scoring prompt" and `references` lists the file with no
  annotation (overlap with GF11).
What is **not** verifiable in-folder (the verification caveat, Point 3):
- Whether `docs/owner-sources/roundtable-agent-ratings.md:57-61, 113` lacks the rubric, and
  whether `prompts.rs:92-93` includes the resource verbatim. Those files are not in `source/`.
  So GF6's central factual premise (the owner source omits the rubric) can be neither confirmed
  nor refuted here.

**Verdict: partially right.** The label "owner's scoring prompt" is genuinely imprecise about
provenance, and that is a legitimate documentation nit; but the finding's specific factual claim
is unverifiable, and no code change is warranted (deleting working rubric instructions would be
wrong).

**What should change (description only, largely shared with GF11):** label `session_scoring.md`
as a *composite resource* — the owner-attributed notice together with the rubric table, bonus
criterion, and JSON response format — rather than implying it is verbatim owner text; annotate it
in `references`; and require verifying the owner source before claiming any portion is owner-
specified. Why: it removes the over-attribution without discarding instructions agents need. No
code change.

## GF7 (Major) — numbers unexplained — RIGHT

`rules[0]` gives "Efficient 10, Alert & Aware 20, Thorough 30, Coordination 40, bonus +5" with
no legend: the numbers could be maxima, weights, or percentages, the 0–5 star scale and the
bonus criterion ("improved the final work beyond just critiquing it", `session_scoring.md:10`)
are absent, and a reader cannot tell what a scorecard holds (a JSON object keyed by participant
name, `session_scoring.md:12-13`). Verified directly against `element.md` and the resource.

**What should change:** expand `rules[0]` to define the scorecard shape, state that the numbers
are maximum points per category (weights), that stars run 0–5 and are scaled by weight/5, that
the bonus is +5 for a true boolean with its criterion, and that one card is worth at most 105.
Why: without this the rule is unreadable. **Merge with GF2** — one rules[0] edit covers both;
GF2 adds the exact formula and the ranking rule, GF7 adds the legend and the card format.

## GF8 (Major) — "identity" / persistence — RIGHT

`rules[1]` and `elephant.design` say ratings are "saved to each agent's identity" and
`elephant.gaps` says they "carry to a later table only if that table resumes the agent's earlier
session". Verified: `app.rs:426-429` defines an identity as its genesis **session** (profiles are
keyed by session, name held inside); `app.rs:430-443, 498-509` give the storage file; the core
reads profiles at `turn.rs:39-40, 521` only when an identity store is present. `element.md` never
defines "identity", never links `code.identity.agent`, and never gives the storage path.

**What should change:** define "identity" in `element.md` (the genesis session / its profile
file), link `code.identity.agent`, give the storage location `$ROUNDTABLE_HOME/identities/<session>.json`,
and state the persistence condition explicitly (a later table must resume the earlier session;
ratings are not attached to a bare name). Why: "saved to identity" is otherwise ambiguous and its
durability cannot be predicted. Merge with GF3 (which supplies who writes and where).

## GF9 (Major) — wants vs `rules[1]`: "results" — RIGHT

The `wants` entry for `code.manager.chat.group` says the element "Collects every agent's ratings
of the others and returns the results" (Intent `send_receive`), while `rules[1]` says agents
"receive the owner's results message". What "results" are (per-card scores, session point totals,
the ranking) and what goes to the manager versus to the agents is not stated in `element.md`.
Verified against the two quoted lines. In the code, "results" = `session_results.md` /
`session_rank.md` (ranking with per-seat points, card counts, and cumulative rating), sent to
seats, while ratings are also emitted as `roundtable.rating` events and written to identity
profiles — there is no in-process return value to the manager.

**What should change:** in `element.md`, define "results" as the session ranking message and
clarify the `wants` wording: it records a functional *want/intent* (`send_receive`), satisfied
through the event stream and identity profiles, not a literal return value to
`code.manager.chat.group`. State what agents receive (the ranking message) versus what the wider
system receives (rating events, persisted points). Why: the current wording implies two different
things called "results" with no definition.

## GF10 (Major) — "table" / endings / scope — RIGHT

`element.md` uses "table" throughout and says "When a table ends" without defining the term, the
end triggers, or whether the evaluator/chair take part. Verified against `element.md`: no such
definitions exist. The code shows only named, `Ready` seats are rated (`turn.rs:421-425, 438`),
so the evaluator/chair (not seats) are out of scope, and departed/non-answering seats are handled
as in GF1/GF5. The engine-level end triggers (`engine.rs:636-650, 791, 840, 903, 906`) are
**reported, not verified** but sit behind `start_rating`.

**What should change:** define "table" (the running Roundtable session with its seats), state what
ends one (chair End, round limit, sustained inactivity — per the engine), state that the rating
round covers the participating seats only (not the evaluator or chair), and describe departed and
non-answering agents. Why: these are preconditions the rule silently assumes. Merge the trigger
list with GF1 so it appears once.

## GF11 (Nit) — references / "owner" — RIGHT

`references` lists two bare paths with no note on what each file is; that `session_scoring.md` is
"the owner's scoring prompt" is only implied; "owner" (used in `rules`, `owner_statements`,
`elephant`) is never introduced. Verified against `element.md`.

**What should change:** annotate each reference (`session_scoring.md` = the scoring prompt sent to
agents; `docs/owner-sources/roundtable-agent-ratings.md` = the owner-source record) and introduce
"owner" (the project author whose requirements/decisions the map records). Why: without it the
phrase "the owner's scoring prompt" is unresolvable. Together with the GF6 reclassification, this
item absorbs GF6's valid residue (the composite-resource label); the two should be one edit, not
two.

## GF12 (Nit) — owner_statements provenance — RIGHT

`owner_statements[0]` is the question "what about agent ratings at the end and saving the agents
rating". `element.md` gives no account of how the specific categories/weights (10/20/30/40, +5)
in `rules[0]` came from it. Verified: the categories derive from `session_scoring.md` (a
`references` entry) and, per `rules.rs:150`, "the owner's earlier system", not from that
statement.

**What should change:** add a short provenance note: the owner statement raised the feature; the
categories, weights, star scale, and bonus come from the referenced `session_scoring.md` / the
owner's earlier system. Why: it explains why the rule has those exact numbers and closes the
traceability gap. Keep it a note, not a rewrite of `owner_statements`.

---

## Consolidated fix plan (avoid duplicate edits)

All edits are to `element.md` unless noted; no rating-logic code change is warranted.

1. **`rules[0]` rewrite (GF1, GF2, GF7, GF10):** define "table" and its endings; state the round
   covers ready, named, remaining seats (not evaluator/chair); list skip conditions (fewer than
   two, forced ends) and no-retry on missing ratings; define the scorecard JSON shape, the 0–5
   star scale, the 10/20/30/40 weights as maxima, the weight/5 formula, the +5 boolean bonus and
   its criterion, silent zeros, and the 105 per-card cap.
2. **`rules[1]` + results definition (GF2, GF5, GF9):** describe the `score_received` receipt,
   the results message as a ranking by summed session points with `rating = prior + session`
   ("unscored" until rated), delivery to ready/named/idle seats and the end-when-sent condition,
   and clarify the manager "returns the results" want versus what agents receive.
3. **New "identity, storage & persistence" section (GF3, GF8):** the core emits
   `roundtable.rating` events and reads profiles; the web host writes
   `$ROUNDTABLE_HOME/identities/<session>.json` via `save_rating`; define identity (genesis
   session), link `code.identity.agent`, state the resume-session carry-over condition; correct
   `elephant.built` so it does not credit `turn.rs` with saving.
4. **New "failure modes" layer (GF4):** JSON brace-extraction, unreadable/non-object rejection,
   zero/multiple name matches, duplicate-name consequence.
5. **References, owner, provenance (GF11, GF12):** annotate references, introduce "owner", and
   record where the categories/weights came from. Note the first-turn `session_profile` line
    (GF5) as a related behaviour.
 6. **GF6 (partially right):** merged into item 5 — label `session_scoring.md` as a composite
    resource (owner notice + rubric + bonus + JSON format), do not claim verbatim owner text,
    keep the rubric. No code change; premise about the owner source stays flagged unverifiable.

## Observations raised during the roundtable (flagged, not GF verdicts)

Two points surfaced from other participants that are worth recording but are **outside** the
GF1–GF12 verdicts. They are marked as possibilities, not established defects, because their
execution depends on code not in this folder or on task scheduling.

- **Possible double-count of the cumulative rating (from `DeifiedArrow-notes.md` item 2).**
  `finish_ratings` reads the stored profile as `prior` and displays `prior.score + session_points`
  (`turn.rs:521-532`). But `save_rating` increments `profile["points"]` for every
  `roundtable.rating` event (`app.rs:500-508`), and those events are published during the round
  (`turn.rs:475-484`) on a bus drained by a separate host task (`app.rs:75-127`). If the host
  persists an early card before the last rater finishes, `prior.score` already contains
  current-session points, which are then added a second time in the displayed rating. This is a
  code-visible ordering hazard, not a measured execution trace; confirming it needs the bus/task
  scheduling detail. It is not among the review findings, so it should be a follow-up note, not a
  change to any GF decision.
- **GF9 wording caution (from `clarifications.TotalLogic.md` item 2).** Do not assert as verified
  that "`code.manager.chat.group` consumes the published events" — the manager's code is not in
  this `source/`. The safe statement, used above, names only this element's two outputs (published
  `RatingGiven` events and the per-seat `session_results` message) and leaves the manager's
  consumption to the manager element. (One other participant's `resolution.TotalLogic.md` GF9
  does say "the manager consumes the returned data"; that claim should be softened to match this
  caveat.)

## Note on the code vs the description

No finding identifies a defect in `rating_points`, `on_rating`, `finish_ratings`, or the host's
`save_rating`: the implementation is internally consistent (clamping, silent zeros, single-target
name matching, atomic profile writes, sum-based ranking all behave as the code comments say). The
reviewers' substantive points are that `element.md` is a high-level map that omits these details
and attributes saving to the wrong component. The right remedy is to enrich the description (and
fix `elephant.built`), not to change the rating code.

## DeifiedArrow — qualifications to the consolidated decision

The following points qualify the broad “description-only, no code defect” conclusion above.

- **GF4:** the corrected two-same-name example above is essential. The predicate `j != i`
  means exactly two same-named seats can manually rate one another. A third rater cannot
  distinguish them, and the automatic prompt omits same-named peers. To satisfy the existing
  “each agent rates every other” requirement for legal name collisions, use stable seat IDs as
  scorecard keys, show names alongside those IDs, and validate against the rater's eligible
  targets. Merely documenting the limitation does not fulfill that requirement. Rejected
  ambiguous cards produce notices; the rejection is not silent, although the final ranking
  shows a reduced received-card count.
- **GF5:** `check_results_done` (`turn.rs:568-570`) also waits while an eligible seat is in
  `Activity::Notified`. “Ends once all are sent” is incomplete: notification replies must
  settle. In addition, `results_sent` is set before `offer`, whose success is ignored
  (`556-557`), so attempted delivery is the verified contract, not guaranteed receipt.
- **GF6:** I disagree with a definitive “not right” verdict. The absent owner-source document
  prevents confirming or refuting the provenance comparison. A resource's use as the scoring
  prompt does not establish that its rubric was authored or approved by the owner. Qualify
  “owner's scoring prompt” as the implemented scoring resource pending inspection of the
  original. Retain the rubric: inaccurate attribution does not justify deleting instructions.
- **GF2:** the cumulative-profile ordering hazard recorded above directly qualifies the phrase
  “earlier profile score.” The code reads a live profile, not a pre-table snapshot. Capture
  the baseline before current-table rating events, or exclude this table's entries, to guarantee
  the stated cumulative result. A regression should let persistence consume an early card before
  the final rater completes; the displayed cumulative total must remain historical plus current
  points exactly once. This is a code recommendation supported by a possible ordering, not a
  claim that the failure was reproduced here.

I agree with naming only the verified outputs under GF9: per-card events and per-seat ranking
messages. No ranking-event publication or manager consumption is established by this snapshot.
The missing-source caveat at the start remains applicable to all decisions.
