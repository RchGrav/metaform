# Resolution of review findings for `code.selector.topic` (next-topic selection)

Resolution synthesizing contributions from ClumsySiduri, HybridMarine, and CleanSorrow, with
MelodicTornado's qualifications below. GF1/GF9's fix direction remains disputed; this is not a
unanimous resolution. Evidence verified directly from this element's `source` files
(`src/turn.rs`, `src/jev.rs`, `resources/topic_sameness.md`). Findings citing `src/engine.rs` /
`src/rules.rs` (files not copied into this element's `source` folder) are marked `[cited]`; no verdict
below asserts a fact about those files that was not independently verifiable from in-scope material.

## Their position

The consistent theme is that the map's `decisions` and `superseded` layers describe a design the built
code does not implement. **No finding requires a code change to be correct.** Most fixes are
description-side: quoting what is actually sent, deleting the dead "all tie" fallback, clearing the
`superseded` layer of live rules, and defining terminology. The single direction dispute (GF1/GF9) is
resolved documentation-side (see below).

---

## GF1 (Blocker) — occupied participants at poll time — RIGHT, description-side

Owner decision "occupied participants at poll time" says occupied participants are left out and "the
table never waits on independent work". The code does the opposite.

Verified (`src/turn.rs`): `start_polling` (269-272) adds seats with `activity != Activity::Idle` to
`pending` and still counts them in `polled`, under the comment "gate: RT-G21 a topic poll waits for
busy agents"; `settle_poll` (285-303) prompts them once idle and drops only a seat whose `state !=
Ready` (left the table). So busy seats are waited for, not left out.

**Direction (the consequential question):** HybridMarine argues the owner decision is a deliberate
2026-11-05 override of the older README §7 default, so the *code* should change (exclude busy seats,
retire RT-G21). We side with CleanSorrow: the code, the active gate RT-G21, and the author's most
recent `elephant.built` (2026-11-07: "turn.rs polls every agent") all agree; the owner decision is the
single outlier and its disposition is unresolved (RT-G21 "owner disposition pending", elephant
"refinement pending"). Changing the code to a single older decision assumes final intent that is not
established.

**Change:** reconcile the description to the implemented behavior — the poll waits for every agent
still at the table (RT-G21), dropping only those who leave. Mark the "occupied participants" decision
as revised-by-implementation / pending owner confirmation rather than silently deleting it. If the
owner confirms "never wait", the code-side change HybridMarine describes becomes the fix.

## GF2 (Blocker) — JEV off or unavailable — RIGHT, description-side (strengthened)

The decision claims with JEV off/down "every proposal ties and all are joined with 'and'". The code
does not implement this.

Verified (`src/turn.rs`): `on_scored` (379-385) on error sets `polling = None` and keeps the current
topic. Further, CleanSorrow's evidence makes the fallback **unreachable**: `jev.rs:161-172`
(`ask()`) returns `Err` via `ok_or` if *any* requested answer is missing, plus `Err` on HTTP failure /
unreadable JSON / out-of-range value — there is no partial `Ok(BTreeMap)` path. Hence
`turn.rs:393`'s `unwrap_or(0.0)` is defensive dead code under the current contract. The decision's
"never waits on JEV" is also false in-scope: `finish_polling` sets `p.scoring` (361), `on_proposal`
discards post-JEV proposals (310), `settle_poll` returns early when scoring is in progress (287) — the
poll blocks on `Scored`. (`[cited]` engine.rs:377-379: with judging off / no key, no poll starts.)

**Change:** replace the decision with: topics require JEV; without judging/JEV no poll is started
`[cited]`; if the scoring request fails, the current topic continues (`on_scored`); a successful batch
scores every pair under `ask`'s all-or-nothing contract, so a "missing pair scores 0" is hypothetical
only. Delete the "all tie and join" claim and drop the "flagged for owner review" status or resolve it.

## GF3 (Blocker) — question wording — RIGHT, description-side (reversed fix)

The "question" decision says JEV is asked whether two proposals express "same underlying intent".
Verified: `topic_sameness.md:1` is literally `{{foo}} is the same as {{bar}}`; `jev.rs:121-123`
substitutes `proposals.pA`/`proposals.pB`. The judging words are not sent.

**Fix is description-side, NOT the template** (reversal of the earlier draft, which proposed rewording
`topic_sameness.md`). Reason: rules[2] — "Sameness is the owner's statement, `{{foo}} is the same as
{{bar}}`" — makes that line the normative owner rule, and `jev.rs:116-117` marks the template as
owner-editable. The "same underlying intent" language (from the "question" decision, dated 2026-11-05)
is the design rationale / interpretation, not extra text sent to JEV. The archaeology finding even
records that the *Python predecessor* asked "Is proposal A similar to B?" and the owner replaced that
loose question with the terse "is the same as".

**Change:** correct the decision to quote the actual shipped prompt and label the intent-gloss as
interpretation: "JEV is asked the owner's bare statement `{{foo}} is the same as {{bar}}` (a `noul`,
so confidence = P(true)); the 'same underlying intent' language is the design rationale, not text sent
to JEV." Leave the template and `jev.rs` unchanged. A reworded template ("expresses the same underlying
intent") would be a *new* owner decision, not a resolution of this finding, and would require changing
rules[2] first.

## GF4 (Major) — superseded rules are still current — RIGHT in substance; drop a false phrase

The `superseded` layer lists "Every participant proposes", "N(N-1)/2 pairs", two-way crediting,
"highest sum wins", "ties joined with 'and'" as superseded. The code still implements all: `turn.rs:352-355`
(`rules::pairs`) builds all pairs; `turn.rs:393` (`rules::select_topic`) sums per-pair confidence with
unjudged→0 (two-way crediting, highest sum); the "ties" decision documents 'and' joining.

**Correction:** the finding's phrase "contradict rules[1]" is false — these items *agree* with rules[1]
almost verbatim (superseded "Every participant proposes" == rules[1] "every agent proposes"; "S_i sum"
== "pairwise sameness is summed"; "highest wins" == "the highest wins"; "'and' ties"
== "ties join with 'and'"). The contradiction is between the `superseded` *label* and the active rules/code, not
with rules[1].

**Change:** remove these five entries from `superseded` (they are current and restated in `rules`/
`decisions`). If the layer is meant to record genuine supersessions, hold the real 2026-11-07 change
there instead (see GF7).

## GF5 (Major) — rules[1] is incomplete — RIGHT, description-side

rules[1] states only the trigger and scoring; observable behaviors are missing.

Verified (`src/turn.rs`): line 327 `Reply::Pass => {}` — PASS yields no proposal; line 323
`rules::truncate_to(..., PROPOSAL_LIMIT)` — proposals cut to 512 chars; lines 343-350 — zero proposals
→ current topic continues and rounds reset, one → `complete_polling(BTreeMap::new())` completed
without JEV. (`[cited]` engine.rs:647 no-limit ending; engine.rs:514-519, 873-881 advance tool.)

**Change:** extend rules[1] with: a PASS gives no proposal; proposals are truncated to 512; zero
proposals continue the current topic; a sole proposal becomes the topic without JEV; the no-limit
ending and advance tool.

## GF6 (Nit) — RT-G11 missing from gates — RIGHT

The `elephant` gaps name RT-G11 for removal, but the `gates` layer lists only RT-G07, RT-G08,
RT-G12, RT-G13, RT-G21. RT-G11 is absent (the finding locates it at engine.rs:872 `[cited]`).

**Change:** add RT-G11 to the `gates` layer or drop it from the elephant gaps.

## GF7 (Major) — superseded records the wrong event — RIGHT

The `superseded` rules are restated almost word-for-word by active `rules`/`decisions`, so no real
2026-11-07 change can be told. The genuine change on that date is the **owner decision "topics off by
default"** (`element.md:111-116`), justified by the vote-gaming exploit ("an agent writes its decision
into its proposal and wins on 'underlying intent'"), plus the elephant note "we need to refine that a
bit" and the owner statement "default is no topics its just the sent in prompt". That decision is absent
from `superseded`.

**Knock-on:** the owner's gaming rationale undercuts the "question" decision's "same underlying intent"
framing — an agent wins precisely *because* the question is about intent. This is a substantive reason
the map is incoherent and supports GF7/GF8/GF9.

**Change:** replace `superseded` contents with the old→new transition ("before: topics on, the table
polls for a next shared focus; after: topics off by default, the table works on the objective it was
sent") and move the five live rules back into `rules`. Reconcile the "question" decision wording with
the on-file template (GF3).

## GF8 (Major) — "need JEV" vs "JEV off, all tie" — RIGHT, description-side

Gate RT-G07 ("Topics are off by default and need JEV") conflicts with the "JEV off or unavailable"
decision ("with JEV off every proposal ties and all are joined"). Verified code resolves it toward "need
JEV": `on_scored` Err path keeps the current topic; message judging (`submit`, 148-155) accepts
unjudged, but that is separate from topic scoring.

**Change:** state it one way: topics require JEV; without JEV no poll is started (or the current topic
continues). Delete the "all tie" fallback (per GF2).

## GF9 (Major) — three polling policies — RIGHT, description-side

`rules` ("every agent proposes"), gate RT-G21 ("waits for every agent"), and the owner decision ("poll
only agents that are not busy; never wait on independent work") are three versions; RT-G12 (late
proposals discarded) adds a fourth. Verified code supports RT-G21 (GF1).

**Change:** reconcile to one behavior — the poll waits for every agent still at the table (RT-G21),
dropping only those who leave; resolve RT-G12 ("late proposals discarded") against it (proposals after
their poll are discarded, consistent with waiting for participants rather than accepting stragglers).
Align with the GF1 direction decision.

## GF10 (Major) — undefined terminology — RIGHT, description-side (with corrected facts)

Terms undefined in the description: JEV, JEV's state, `{{foo}}`/`{{bar}}` templating, ACP v1 vs v2,
"occupied", the "30K-token case-selection alternative".

**Factual corrections to the glossary (CleanSorrow):**
- "JEV's state" is the JSON `state` object in the request (`jev.rs:154`: `json!({"model",
  "state", "questions"})`); for topic comparison it is `{"proposals": {"p0": ..., "p1": ...}}`
  (`turn.rs:356-358`). It is **not** the token budget (a separate constant).
- The contribution-evaluation constants are `32_000` (`jev.rs:64`,
  `STATE_PLUS_QUESTION_TOKENS`) and `64_000` (`jev.rs:66`, `REQUEST_TOKENS`). No supplied evidence
  connects those constants to the historical "30K-token case-selection alternative". That alternative
  is undefined; it cannot be called a 2K discrepancy or corrected to 32K merely from these constants.
- "occupied" maps to `activity != Activity::Idle` (`turn.rs:269`, code says "busy").
- "inserted into running ACP v2 sessions" has no counterpart in any in-scope file — evidence for GF1.

**Change:** add an accurate glossary: JEV = the judge model; state = the request's `state` object;
`{{foo}}`/`{{bar}}` → `proposals.pA`/`proposals.pB`; occupied = activity != Idle; ACP v1 vs v2 =
the session model (with the v2 poll-insertion capability **not implemented in the supplied files**);
remove the unexplained historical alternative from the operative description or supply its original
source. Keep the unrelated contribution-evaluation token limits separate.

## GF11 (Major) — RT-G11 absent; RT-G13 unreconciled — PARTLY RIGHT

The RT-G11 half duplicates GF6 (absent from gates yet named in gaps) — upheld. RT-G13 ("Topic
proposals are cut at 512") is active and implemented (`turn.rs:322-323`).

**Rejected framing:** the finding's "contradicts the owner's no-truncation rule" is unsupported. There
is no such rule in element.md; the only no-cut rule (`turn.rs:128-131`, "blocked, never cut (owner)")
governs **replies** over the reply limit, whereas RT-G13 truncates **topic proposals**. Different
objects → no literal contradiction.

**Change:** description-side — add the 512-char cut to `rules`; give RT-G13 a disposition (keep as a
deliberate exception, or implement the proposed removal); add RT-G11 to `gates` or drop it from
`gaps`.

## GF12 (Nit) — "or every agent passing" redundant — RIGHT

"Nothing accepted (or every agent passing)": an all-pass round already has nothing accepted, so the
second disjunct is a subset of the first; the "or" is either vacuous or smuggles in an unstated stronger
meaning (e.g. "everyone passed and nobody worked"). Decidable from element.md alone. The overlap with
the engine's no-limit ending is `[cited]` engine.rs:647, corroborated by GF5.

**Change:** simplify rules[1] to "two rounds with nothing accepted start a poll", and add a note
distinguishing it from the no-limit ending (which ends the table rather than polling when the topic had
no input). If "every agent passing" meant something specific, define it.

---

## Net verdicts

| Finding | Verdict | Fix in |
| --- | --- | --- |
| GF1 | Right | description (decision + RT-G21 disposition); code only if owner confirms "never wait" |
| GF2 | Right | description (decision); fallback unreachable under `ask`'s all-or-nothing contract |
| GF3 | Right | description (question decision) — **not** the template |
| GF4 | Right in substance; drop "contradict rules[1]" | description (superseded layer) |
| GF5 | Right | description (rules[1]) |
| GF6 | Right (Nit) | description (gates / elephant gaps) |
| GF7 | Right | description (superseded layer; record the real 2026-11-07 change) |
| GF8 | Right | description (rules[1] / RT-G07 / decision) |
| GF9 | Right | description (rules, gates, owner decision) |
| GF10 | Right, two glossary facts corrected | description (add accurate glossary) |
| GF11 | Partly right | description (gates, rules); reject "no-truncation rule" framing |
| GF12 | Right | description (rules[1]) |

No finding requires a code change to be correct. The one change worth *considering* as a new design
decision — not a resolution — is rewording the sameness template to "expresses the same underlying
intent" (GF3); the owner's 2026-11-07 gaming rationale argues against it.

## MelodicTornado's final qualifications

**GF1/GF9: the documentation-only direction is disputed.** RT-G21's exact status in `element.md`
is "active, owner disposition pending", not "owner-designed". `elephant.built` is explicitly an
account of what was built; "polls every agent" does not establish owner approval of waiting for
independent work. No supplied owner statement revokes the explicit occupied-participant decision.
The implemented queue is established, but calling the owner decision "revised-by-implementation"
would incorrectly turn implementation into authorization. My recommended resolution remains a code
change to honor that decision: skip occupied v1 seats, insert requests into running v2 sessions using
their supported capability, and do not condition poll completion on independent work ending. Simply
skipping all busy seats would also omit the owner's v2 requirement. Document the current discrepancy
and keep the owner decision intact; if the group defers the code change, record that as a disputed
disposition rather than a confirmed reversal of owner policy.

**GF9: late rejection is not another participation policy.** RT-G12 checks whether a poll exists,
the seat was asked, and scoring has started (`turn.rs:307–316`). Those boundaries are compatible
with either waiting for busy participants or excluding them. The finding is right about the
busy-seat contradiction, but not about RT-G12 adding a third or fourth competing policy.

**GF4: delegated arithmetic is not locally verified.** `rules::pairs` and `rules::select_topic` are
calls into the missing `rules.rs`. They demonstrate delegation, not the exact pair count, symmetric
credit, maximum calculation, or tie joining. The description's status contradiction is independently
clear; the exact arithmetic remains reviewer-cited evidence until that file is inspected.

**GF11: reject the unsupported assertion, not every possible scope conflict.** The record supplied
does not establish a general owner no-truncation rule. Conversely, a proposal is itself an agent
reply; different labels alone do not prove an owner reply policy excludes proposals. The proposal
handler demonstrably truncates; the general contribution handler blocks over-limit contributions.
The scope of the owner's original instruction must be established before concluding whether this is
an authorized exception. The definite documentation fix is to record current truncation and its
proposed removal without inventing an approved disposition.
