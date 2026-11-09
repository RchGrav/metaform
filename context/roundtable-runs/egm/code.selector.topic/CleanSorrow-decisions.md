# CleanSorrow — independent audit of the 12 findings for `code.selector.topic`

Scope note: `source/` contains exactly three files: `crates/roundtable/src/turn.rs`,
`crates/roundtable/src/jev.rs`, `crates/roundtable/resources/topic_sameness.md`. Eight findings also
cite `src/engine.rs` and/or `src/rules.rs`; those files were **not** copied into this element. I mark
such line references `[cited]`. A finding can still be decided when its core claim is verifiable from
`element.md` itself or from the three in-scope files. Nothing below asserts a fact about engine.rs or
rules.rs that I could not read.

## Where I disagree with the current `resolution.md` draft

### GF3 — the draft's remedy is backwards (fix the description, NOT the code)

The draft says: "reword `topic_sameness.md` ... E.g. `{{foo}} expresses the same underlying intent as
{{bar}}`." That would change the code to violate the spec.

- `element.md` rules[2]: "Sameness is the owner's statement, `{{foo}} is the same as {{bar}}`, with
  the proposals named in JEV's state." The owner's terse statement is the normative rule.
- `turn.rs:356-358` builds exactly that state: `{"proposals": {"p0": ..., "p1": ...}}`.
- `jev.rs:118-123` + `resources/topic_sameness.md:1` send exactly the owner's statement with those
  names substituted.
- Archaeology (`prompts.xml:646-648`) records the *Python predecessor* asking "Is proposal A similar
  to proposal B?" where true meant "concern a shared subject, question or direction". The owner's
  "is the same as" line is the deliberate replacement for that loose question. The "question"
  decision (2026-11-05) correctly explains the rationale (true = same intent, no negation because
  JEV reads negation literally) but then overstates it by claiming JEV "is asked whether the two
  proposals express the same underlying intent: what the group would actually address next". No such
  words are sent.

So GF3 is **right** that a mismatch exists, but the mismatch is the *description over-describing* the
question. Correct the decision to: "JEV is asked the owner's bare statement `{{foo}} is the same as
{{bar}}` (a `noul`, so the confidence is P(true)); the 'same underlying intent' language is the
design rationale, not extra text sent to JEV." Leave `topic_sameness.md` and `jev.rs` alone. Changing
the template to "expresses the same underlying intent as" is a plausible product improvement, but it
is a *new decision*, not a resolution of this finding, and it would need rules[2] changed first.

### GF2 — new evidence: the "all tie" fallback is unreachable by JEV's own contract

The draft correctly kills the "all tie" claim but understates why.

- `jev.rs:161-172`: `ask()` iterates **all** requested questions and returns `Err` via
  `ok_or(format!("no {} answer for {name}", ...))` if any single answer is missing, plus `Err` on
  HTTP failure, unreadable JSON, or an out-of-range value. There is no code path that produces a
  partial `Ok(BTreeMap)`.
- Therefore `turn.rs:393`'s `.unwrap_or(0.0)` (unjudged pair → 0.0) is defensive dead code under the
  current JEV contract. The decision's "A pair JEV did not judge scores 0" is true only as a
  hypothetical, and "every proposal therefore ties and all are joined" has **no reachable input**.
- `on_scored` (`turn.rs:377-386`) on `Err` sets `polling = None`, notices, resets rounds, and leaves
  the topic unchanged. No join.
- The decision's premise "Topic selection never waits on JEV" is also false in-scope:
  `finish_polling` sets `p.scoring = Some(ticket)` (361), `on_proposal` discards proposals "after the
  proposals went to JEV" (310), and `settle_poll` returns early when `scoring.is_some()` (287). The
  poll demonstrably blocks on the `Scored` result. (This is separate from message judging, which
  genuinely is non-blocking: `submit` at 148-155 accepts unjudged immediately.)

Verdict: GF2 **right**. Change = description. Replace the decision with: "Topics require JEV.
Without judging/JEV, no poll is started [cited engine.rs:377-379]. If the scoring request fails, the
current topic continues (`on_scored`). A successful batch scores every pair; a missing pair would
score 0 but cannot occur under `ask`'s all-or-nothing contract." Also drop the "flagged for owner
review" status or resolve it.

### GF4 — the finding's own wording contains a false claim

GF4 says the superseded items "are current (src/rules.rs:122-148) and **contradict rules[1]**". They
do not contradict rules[1]; they *agree* with it almost verbatim:

| superseded (2026-11-07) | rules[1] |
| --- | --- |
| "Every participant proposes a next topic." | "every agent proposes" |
| "Each pair's confidence is credited to both proposals; S_i = sum ..." | "pairwise sameness is summed" |
| "Highest sum wins; no 70% threshold." | "the highest wins" |
| "Two tied winners are joined with 'and'." | "ties join with 'and'" |

Verdict: GF4 **right in substance, wrong in that phrase**. The contradiction is between the
`superseded` *label* and the active `rules`/code — not with rules[1]. Resolution.md should say so
explicitly rather than repeating "contradict rules[1]". In-scope confirmation: `turn.rs:352-355`
calls `rules::pairs(proposals.len())` (N(N-1)/2) and `turn.rs:393` calls `rules::select_topic` with a
per-pair confidence lookup. `[cited]` rules.rs:122-148 for the sum/tie internals.

### GF7 — make the real 2026-11-07 change concrete

The genuine change on 2026-11-07 is the **owner decision "topics off by default"**
(`element.md:111-116`), justified by the vote-gaming exploit ("an agent writes its decision into its
proposal and wins on 'underlying intent'"), plus the `elephant` note "we need to refine that a bit"
and the owner statement "default is no topics its just the sent in prompt". That decision is absent
from the `superseded` layer, which instead lists five *live* rules. So `superseded` is not merely
duplicated — it records the wrong event. Fix: replace its contents with the old→new transition,
i.e. "before: topics on, the table polls for the next shared focus; after: topics off by default,
the table works on the objective it was sent" and move the five live rules back into `rules`.

Note the knock-on: the owner's gaming rationale undercuts the "question" decision's "same underlying
intent" framing — writing your decision into your proposal wins precisely *because* the question is
about intent. That is a substantive reason the map is incoherent, and it supports GF7/GF8/GF9.

### GF10 — two factual corrections to the draft's glossary

- "JEV's state = the token budget incorporated into the request" is wrong. JEV's state is the JSON
  `state` object in the request (`jev.rs:154` `json!({"model", "state", "questions"})`); for topic
  comparison it is `{"proposals": {...}}` (`turn.rs:356-358`). The token budget is a separate
  constant.
- "30K" should be **32_000**: `jev.rs:64` `STATE_PLUS_QUESTION_TOKENS: usize = 32_000` (and
  `REQUEST_TOKENS = 64_000` at line 66). The `superseded` entry says "30K-token case-selection
  alternative"; the map and the constant disagree by 2K. (The "case-selection alternative" itself is
  only recorded in `superseded`, so GF10 is right that it is undefined.)
- "occupied" in the owner decision maps to `activity != Activity::Idle` in `turn.rs:269` (the code
  says "busy"); "inserted into running ACP v2 sessions" has no counterpart anywhere in the three
  in-scope files — that is exactly why GF10 is right, and it is further evidence for GF1.

Verdict GF10 **right**, but the glossary must be accurate.

### GF11 — "the owner's no-truncation rule" is not in the description

GF11 says RT-G13 "contradicts the owner's no-truncation rule". There is no such rule in
`element.md`. The only no-cut rule in-scope is `turn.rs:128-131`: "A message over the limit is
blocked, never cut (owner)" — that governs **replies** over the reply limit, whereas RT-G13
(`turn.rs:322-323`) truncates **topic proposals** at `PROPOSAL_LIMIT` (512). Different objects, so no
literal contradiction. What *is* true and unresolved: the description's `rules` never mentions the
512-char cut, the gate says "removal proposed" while the code actively truncates, and the elephant
gaps name a gate (RT-G11) that is not in the gates layer. Verdict: GF11 **partly right** — uphold the
RT-G11 half and the "not reconciled" half; reject the "contradicts the owner's no-truncation rule"
framing. Fix = description: add the 512 cut to `rules`, give RT-G13 a disposition, add RT-G11 to
`gates` or drop it from `gaps`.

### GF12 — first half is pure logic, no code needed

"Nothing accepted (or with every agent passing)": a round in which every agent passes has, by
definition, nothing accepted. So the second disjunct is a subset of the first; the "or" is either
vacuous or smuggles in an unstated stronger meaning (e.g. "everyone passed *and* nobody worked").
This is decidable from `element.md` alone. The "overlaps the engine's no-limit ending rule" half is
`[cited]` engine.rs:647 and is corroborated by GF5's first bullet. Verdict **right**. Fix =
description: "two rounds with nothing accepted start a poll", plus an explicit note distinguishing
it from the no-limit ending (which ends the table rather than polling when the topic had no input).

## Where I agree with the draft

- **GF1 right.** `turn.rs:269-272` puts `activity != Idle` seats into `pending` *and* `polled`;
  `turn.rs:285-303` `settle_poll` asks them once idle and only drops a seat whose `state != Ready`
  (left the table). The comment at 270 literally says "gate: RT-G21 a topic poll waits for busy
  agents". The owner decision ("left out", "never waits") is the outlier; `elephant.built` ("polls
  every agent") and active gate RT-G21 agree with the code. Fix = description. Caveat: engine.rs:504-507
  `[cited]`. Because this is an *owner* decision, the right move is to mark it revised-by-owner-implementation
  and resolve RT-G21's "owner disposition pending", rather than silently deleting it.
- **GF5 right.** In-scope: `turn.rs:327` PASS → no proposal; `turn.rs:323` 512 cut; `turn.rs:343-350`
  zero → current topic continues + rounds reset, one → `complete_polling(BTreeMap::new())` with no
  JEV. The advance-tool and no-limit bullets are `[cited]`. Fix = description (extend rules[1]).
- **GF6 right** (Nit). `gates` lists G07, G08, G12, G13, G21 — no G11; `elephant.gaps` names G11.
- **GF8 right.** Real contradiction between RT-G07 "need JEV" / rules[1] "with ... JEV available"
  and the "JEV off or unavailable" decision. Code in-scope resolves it toward "need JEV"
  (`on_scored` Err path; `submit` accepts messages unjudged but that is message judging, not
  topic scoring). Fix = description.
- **GF9 right.** Three (not four) versions in the finding: rules[1] "every agent proposes", RT-G21
  "waits for every agent", owner decision "only non-occupied, never wait", plus RT-G12 "late
  proposals discarded" as a fourth consideration. The code (GF1) supports RT-G21. Fix =
  description, one reconciled statement.

## Net verdicts

| Finding | Verdict | Fix in |
| --- | --- | --- |
| GF1 | Right | description (decision + RT-G21 disposition) |
| GF2 | Right | description (decision); JEV contract makes fallback unreachable |
| GF3 | Right, but draft's remedy is backwards | description (question decision), **not** the template |
| GF4 | Right in substance; "contradict rules[1]" is a false phrase | description (superseded layer) |
| GF5 | Right | description (rules[1]) |
| GF6 | Right (Nit) | description (gates / elephant gaps) |
| GF7 | Right | description (superseded layer, record the real 2026-11-07 change) |
| GF8 | Right | description (rules[1] / RT-G07 / decision) |
| GF9 | Right | description (rules, gates, owner decision) |
| GF10 | Right, two glossary facts in draft are wrong | description (add glossary) |
| GF11 | **Partly right** | description (gates, rules); reject "owner's no-truncation rule" framing |
| GF12 | Right | description (rules[1]) |

No finding requires a code change to be *correct*; the theme is that the map's `decisions` and
`superseded` layers describe a design the built code does not implement. The one code change worth
considering is GF3's "expresses the same underlying intent as" wording — but that is a new design
decision (and the owner's 2026-11-07 gaming rationale argues against it), not a finding resolution.
