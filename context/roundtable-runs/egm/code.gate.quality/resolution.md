# Resolution of review findings — `code.gate.quality` (JEV contribution evaluation)

Reviewed by **RiskySaber**.

## Verification scope

I checked every finding against the copied source: `src/jev.rs`, `src/turn.rs`, and
`resources/jev/*` + `resources/feedback/*`. The findings also cite `src/prompts.rs`,
`src/engine.rs`, `src/rules.rs` and `docs/gate-registry.yaml`, which are **not** in this
`source/` folder. Those claims are nevertheless corroborated by what is here:

- `turn.rs:216` calls `prompts::rejected(&failed)`; `turn.rs:225` puts `format!("{name} {value:.2}")` into the published `Contribution` event. The `resources/feedback/` files (`prefix.md`, `contribution.md`, `usefulness.md`, `relevance.md`, `value-0/1/2.md`, `auditability-0/1/2.md`, `too_long.md`) are present and are exactly the "owner's fixed feedback files" GF1/GF2 describe.
- `turn.rs:113-115` returns `None` for a floor contribution and defers the outcome to `on_judged` (`turn.rs:184-234`); `turn.rs:171-172` sets `judging_floor`/RT-G10. This is the "next turn waits" behaviour GF3/GF9 cite, confirmable without `engine.rs`.
- `turn.rs:11` imports `GATE_PASS`/`SCORE_PASS`, consistent with the 0.70 / 3.0 thresholds in `rules[2]`.

So the findings can be adjudicated on this evidence. Where a fix names `prompts.rs` or `engine.rs` I say so explicitly rather than pretending to have read them.

## Verdicts at a glance

| Finding | Verdict | Primary change target |
|---|---|---|
| GF1 Blocker | **Right** | description — the two `wants` lines (16, 19) |
| GF2 Blocker | **Right** | description — decision `reasons` (94-98); align with `rules[3]` |
| GF3 Blocker | **Right** | description — decision `JEV is optional` (106-112); also stale code comments + one genuine owner-intent concern |
| GF4 Blocker | **Right** | description — decision `judging context` (100-104) |
| GF5 Major | **Right** | description — `rules[4]` (47) and adjacent rules |
| GF6 Nit | **Right** | description — `superseded` layer (138-157) and `rules[5]` (48) |
| GF7 Major | **Right** | description — reconcile `wants` / `rules` / decision `reasons` |
| GF8 Major | **Right** | description — reconcile decision `judging context` with `rules[4]`; define the limits and `topic`-when-off |
| GF9 Major | **Right** | description — decision (110), `rules[5]`, `gates` layer; add RT-G10; consider a code timeout |
| GF10 Major | **Right** | description — add a definitions/glossary section; name the rubric files |
| GF11 Nit | **Right** | description — `superseded` layer annotations |
| GF12 Nit | **Right** (with one nuance) | description — reword the `elephant` gap; optionally persist JEV requests |

**All twelve findings are right.** None is a false positive. That is less surprising than it
looks: GF1/2/3/4, GF6/11 and GF7/9 are two reviewers independently spotting the *same*
root cause — the description still carries text from the superseded three-condition,
"never waits" design, while the code implements the 7 Nov 2026 five-check spec. Below I
resolve each on its merits and flag the few places where the finding is right but
slightly overstated or where a code change, not just a description change, is warranted.

---

## GF1 — Blocker — `wants` (both lines) — **Right**

**Why.** `wants` line 16 says "Accepts or vetoes each transmitted contribution against the
**three 70% conditions**, with veto reasons"; line 19 says JEV "Returns a confidence for
each of the **three** contribution conditions, **with reasons for any that fall short**".
The code has five checks: three `noul` gates (`jev.rs:43-47`) and two 0-5 `score`s
(`jev.rs:50-53`), assembled into one request (`jev.rs:55-59`). `Jev::ask` returns
`BTreeMap<String, f64>` — numbers only (`jev.rs:152-175`); there is no prose "reason"
field anywhere in the reply parsing (`jev.rs:168-172`). A message that passes all three
gates can still be vetoed by `value` or `auditability` (`turn.rs:207-210`), so "three
conditions" is not even a harmless shorthand — it is an incomplete description of the
acceptance rule. The "reasons" delivered to the author come from the owner's fixed
feedback files in `resources/feedback/` via `prompts::rejected(&failed)` (`turn.rs:216`),
not from JEV.

**What should change (description).**
- `wants` line 16: replace "the three 70% conditions" with "five checks: three gates at
  0.70 and two 0-5 scores at 3.0". Keep "with veto reasons" but qualify it: the reasons
  are the owner's fixed per-check feedback, not JEV output.
- `wants` line 19: replace with "Returns one numeric answer for each of the five checks in
  a single OpenRouter request; no prose reasons". Delete "with reasons for any that fall
  short".

**Why that change.** It makes the dependency lines describe the implemented contract
(`rules[0]`, `rules[2]`, `jev.rs:43-59`, `jev.rs:152-175`). No code change: the code is
the newer, owner-designed behaviour (`decisions` 114-119, 128-133); the dependency lines
are stale text inherited from the superseded three-condition design.

---

## GF2 — Blocker — decision `reasons` — **Right**

**Why.** The decision (lines 94-98) says "The veto reason delivered at the next turn names
each failed condition in plain words **with its confidence**". Two code paths exist:
- author: `turn.rs:216` pushes `prompts::rejected(&failed)` into `seat.notices`, delivered
  at the next discussion turn (`turn.rs:52-55`, RT-G16). Per the finding (`prompts.rs:44-54`)
  and the `resources/feedback/` files, these lines are `- <Label>: <owner feedback>`
  prefixed by `prefix.md` — no numbers.
- chair/event: `turn.rs:225` sets `reasons: failed.iter().map(|(name, value)| format!("{name} {value:.2}"))` on the published `Contribution` event.

So confidences/scores exist, but they go **only** to the chair-facing event, never to the
author. `rules[3]` (line 46) already describes the author's notice correctly ("the owner's
prefix and one line per failed check, with the owner's feedback for that check or score
band") — the decision contradicts the element's own rule.

**What should change (description).** Keep the decision's first clause ("JEV returns
probabilities, not prose") — it is correct and agrees with GF1 — and replace the second
clause with: "the veto reason at the next turn names each failed check in plain words with
the owner's fixed feedback for that check or score band; the numeric confidences and scores
are published on the chair-facing `Contribution` event, not shown to the author." Cross-
reference `rules[3]`.

**Why.** It removes a false claim and resolves the internal contradiction with `rules[3]`
without touching code. Adding confidences to the author's notice would be a *design*
change, not a documentation fix, and would need an owner decision; the current author
notice matches the owner's "tell the author exactly why" design (`elephant`, line 181).

---

## GF3 — Blocker — decision `JEV is optional` — **Right** (three false claims, one real owner-intent tension)

**Why.** Decision line 110 claims (a) "contributions are **truncated to the allowance** and
distributed unjudged" when judging is off, (b) JEV "does not answer within a **short
deadline**", and (c) "the table **never waits on JEV**". All three are false:
- (a) `turn.rs:148-150` calls `accept(judgement, ...)` with the full text and a note; nothing
  is truncated. Over-limit messages are *blocked, not cut* (`turn.rs:127-145`, RT-G02), and
  they never reach JEV. (A stale doc comment at `turn.rs:124` still says "Truncate, then
  judge..." — see below.)
- (b) `jev.rs:3` states "No timer: it gets a reply or an error" (marked `(O)`, i.e. owner
  spec). `Jev::ask` (`jev.rs:152-160`) has no timeout; the spawned task (`turn.rs:177-180`)
  awaits a reply or an error.
- (c) `turn.rs:171-172` sets `judging_floor = Some(ticket)` under RT-G10; `resolve_reply`
  (`turn.rs:113-115`) defers the floor outcome until `on_judged`. The next floor turn waits
  for the verdict. Combined with (b), an unresponsive JEV can stall the table indefinitely.

Note the awkward history: the decision's `supersedes` note (line 111) rejects "the table
waits while JEV is unavailable", yet `jev.rs:3` (also owner-attributed) mandates no timer and
`turn.rs:171` mandates the wait. Two owner statements conflict; the code follows `jev.rs:3`.

**What should change.**
1. **Description (decision, lines 106-112):** delete "truncated to the allowance" (off ⇒
   shared unjudged in full, with the note `unjudged: judging is off` / `unjudged: no
   OpenRouter key`); delete "short deadline" (there is no JEV-specific timer; failure means
   a transport/HTTP error or an unreadable/out-of-range answer). **Do not resolve the
   "never waits" contradiction by describing the wait** — see the Reconciliation section
   below. Keep the owner's actual ruling — optional, never halts on failure, share
   unjudged, mark, notify chair — which the code does honour on `Err`
   (`turn.rs:199-203`, `turn.rs:163-167`).
2. **Code comments:** fix `turn.rs:124` ("Truncate, then judge...") and `turn.rs:2`
   ("judging (which never holds the table)"). Both contradict RT-G10 and the length-block
   behaviour, and are the likely source of the stale description text.
3. **Owner-intent concern (flag, do not silently paper over):** no timer + RT-G10 means a
   hung JEV *can* halt the table, which is what the owner's statement (line 109) explicitly
   warns against. Either add a short timeout in `Jev::ask`/the spawned task so a silent JEV
   becomes an `Err` (making the decision's "short deadline" true and honouring "never
   halts"), or record explicitly in the description that this is an accepted deviation.
   This is the one finding where a **code** change is arguably required, not just wording.

---

## GF4 — Blocker — decision `judging context` — **Right**

**Why.** Decision line 103 says JEV sees "the **objective**, the current topic, the accepted
contributions **of the current topic** (newest whole messages first, oldest dropped first)
and the candidate", and that "the **window size is a setting**". `contribution_state`
(`jev.rs:78-103`) builds exactly `{"topic", "conversation", "new_message"}` with **no
objective**; `conversation` is the accepted messages *and chair entries* of the last
`HISTORY_ROUNDS`=4 completed rounds plus the current round, **grouped by round**
(`by_round`, `jev.rs:105-114`) — not "the current topic's messages". `HISTORY_ROUNDS`,
`STATE_PLUS_QUESTION_TOKENS` and `REQUEST_TOKENS` are `pub const` (`jev.rs:62-66`), not
settings. `rules[4]` (line 47) already states the state correctly; the decision is stale.

**What should change (description).** Replace the decision with the `rules[4]`/code
contract: state = `topic`, `conversation` (last four completed rounds + current, grouped by
round, oldest dropped first until both token limits are met), `new_message`; **no
objective**; the window and both token limits are compile-time constants, not settings.
Drop "Jev's documentation says accuracy falls..." or move it to a note with a link (GF10).

**Why.** It removes a Blocker-level mismatch. The objective is genuinely absent from JEV's
state — the participant prompt containing the objective (`turn.rs:70-78`) is not logged as
an `Entry`, so it is not in `conversation`. No code change needed.

---

## GF5 — Major — `rules[4]` omissions — **Right**

**Why.** All five sub-claims are verifiable:
- `conversation` includes Chair guidance: `jev.rs:85` maps `Entry::Chair` to
  `{"name":"Chair","text":...}`. `rules[4]` says "accepted messages" only.
- A message that cannot fit is shared unjudged with a loud notice: `jev.rs:97-98` returns
  `Err` when even an empty conversation fails the limits; `turn.rs:163-167` calls
  `notice("error", ...)` and `accept(..., Some(format!("unjudged: {reason}")))`.
- The topic is the one from when the turn started: `turn.rs:147` stores
  `self.seats[i].prompt_topic` in the `Judgement`; `turn.rs:160` reads
  `self.topics[judgement.topic - 1]`, not the live table topic.
- Missing or out-of-range answers are errors: `jev.rs:168-171` (`ok_or("no ... answer")`
  and `outside 0..{top}`) → `Err` → unjudged (`turn.rs:199-203`).
- After-work replies do not block: `turn.rs:170` gates `judging_floor` on
  `!judgement.after_work`; `turn.rs:116-120` records the acceptance separately.

**What should change (description).** Expand `rules[4]` (or add short rules) to state:
`conversation` contains accepted messages **and Chair guidance**; `topic` is captured from
the turn's prompt; if even an empty conversation cannot fit, the message is **shared
unjudged with a loud error notice** (an operational error, not a rejection); missing or
out-of-range JEV answers are treated as JEV failure; after-work replies do not set the
floor-wait gate. No code change — these are documented-behaviour gaps.

---

## GF6 — Nit — `superseded` / `rules[5]` — **Right**

**Why.** The `superseded` layer (line 154) lists "**Evaluation happens once, before
distribution**" as superseded, yet `submit` (`turn.rs:125-182`) does exactly one evaluation
before sharing, and `rules[0]` says "One JEV request per message". It is still current.
`rules[5]` (line 48) says "the message is shared unjudged and **the error is shown**" for
"off, has no key, or fails"; for off/no-key (`turn.rs:148-155`) there is no `notice("error")`
— only the `Contribution` event `note` (`unjudged: judging is off` /
`unjudged: no OpenRouter key`). A loud error notice exists only for the failure/state-too-big
paths (`turn.rs:164`, `turn.rs:200`).

**What should change (description).** Remove "Evaluation happens once, before distribution"
from `superseded` (or mark it "still current"). Rewrite `rules[5]` to separate the cases:
off / no key ⇒ shared unjudged with an event note, no error; JEV failure / state-too-big ⇒
shared unjudged with a loud error notice, an event note, and the chair notified. Also fix
the stale `turn.rs:124` "Truncate" doc comment (shared with GF3). Overlaps GF11; treat
GF6 as the `rules[5]` half and GF11 as the `superseded` half.

---

## GF7 — Major — comprehension: `wants` vs `rules` vs decision `reasons` — **Right**

**Why.** Three parts of the description disagree about the same facts: `wants` lines 16/19
say "three 70% conditions" and "three conditions with reasons" (upstream wants JEV to
return "reasons for any that fall short"); `rules[0]`/`rules[2]` say five checks including
two 0-5 scores at 3.0; decision `reasons` (line 96) says "JEV returns probabilities, not
prose" yet also says the veto names each condition "with its confidence" (GF2); `rules[3]`
says the author gets the owner's fixed feedback. The single word "reasons" is used for
three different things: JEV prose that does not exist, the author's feedback lines, and the
`{name} {value:.2}` event strings (`turn.rs:225`).

**What should change (description).** One consolidated edit: five checks (three gates at
0.70, two scores at 3.0, all must pass); JEV returns numbers only; the author's per-check
"reasons" are the owner's fixed feedback files (`rules[3]`); the numeric values are the
chair-facing event `reasons`. Fix `wants` lines 16/19, the decision `reasons`, and the
upstream phrase "with reasons for any that fall short". No code change. (This is the
comprehension mirror of GF1/GF2; resolving those plus this one edit fixes all three.)

---

## GF8 — Major — comprehension: decision `judging context` vs `rules[4]` — **Right**

**Why.** Decision (103) gives objective + topic + "current topic's messages" under a single
"64K limit"; `rules[4]` (47) gives topic + last four rounds + current round + `new_message`
under "32,000 and 64,000 token limits". The two limits are indeed unexplained in the
description; in code `STATE_PLUS_QUESTION_TOKENS`=32,000 is the budget for *state + the
longest single question* and `REQUEST_TOKENS`=64,000 for *state + all questions*
(`jev.rs:63-66`, `jev.rs:89-96`), measured by the 3-bytes-per-token estimate
(`jev.rs:68-72`). The objective appears only in the (wrong) decision, not in `rules[4]` and
not in the code (GF4). What `topic` holds when topics are off is unstated: `turn.rs:160`
indexes `self.topics[judgement.topic - 1]` regardless of `topics_active()`
(`turn.rs:57`), so a topic value is always present (the initial/standing topic) but the
description never says so.

**What should change (description).** Reconcile the decision to `rules[4]` as in GF4; add a
sentence explaining both constants and that they are constants checked against an
*estimate*, not provider counts (this also supports the `elephant` gap at line 188); state
what `topic` contains when topics are off. No code change.

---

## GF9 — Major — comprehension: owner decision / `rules` / RT-G10 — **Right**

**Why.** Same three contradictions as GF3/GF6 seen from the consistency angle: "truncated
to the allowance" (line 110) vs truncation removed (`turn.rs:127-145`); "the error is
shown" (`rules[5]`, line 48) vs the decision's "marked 'unjudged: JEV unavailable' in the
discussion record, and the chair is notified on the event bus" — the description never
says *where* the error is shown or that these are the same mechanism (`notice("error")` +
`Contribution.note` + event, `turn.rs:200-201`, `turn.rs:242-254`); and RT-G10
(`turn.rs:171`) "the next turn waits for JEV's verdict" vs "the table never waits on JEV".

Note also that this element's `gates` layer (lines 159-175) lists only RT-G01 and RT-G17.
RT-G10 is a JEV-evaluation gate in the code but is absent here — which is why the
description can assert "never waits" without confronting it. (RT-G02, the length block at
`turn.rs:127`, is likewise absent.)

**What should change (description, plus one code consideration).**
- Remove the truncation claim; define "the error is shown" precisely as a loud chair
  `notice("error")` plus a `Contribution` event note, and say it applies to JEV
  *failures* and the state-too-big case, not to off/no-key (GF6).
- Add **RT-G10** to the `gates` layer with a one-line description. **Do not** resolve
  "the table never waits on JEV" by entrenching the wait — see the Reconciliation section
  below: this is a code-vs-owner conflict to escalate, with the floor-wait recorded as a
  gap, not a ratified behaviour. (RT-G02 is worth adding too, since `submit` owns it.)
- Reconcile with the engine element that owns RT-G10 so the two elements do not disagree.
- **Code:** as in GF3, consider a short timeout. `jev.rs:3` attributes "No timer" to the
  owner, which conflicts with the decision's "short deadline"; one of the two must be
  corrected, and the description must not claim a deadline the code lacks.

---

## GF10 — Major — terminology — **Right**

**Why.** A first-time reader is given no definitions for: JEV (never expanded or linked —
it is the judge model behind the OpenRouter `decisions` endpoint, `jev.rs:16-18`, `uri`
`crates/roundtable/src/jev.rs`); "Jev's documentation" (line 103, no link); "owner's
prefix" (`rules[3]`; it is `resources/feedback/prefix.md`, present and readable: "We're
sorry your message was not able to be submitted for the following reason(s):"); "score
band" (`rules[3]`; the failing score levels — scores ≥ 3.0 pass, `turn.rs:207-210` — with
files `value-0/1/2.md` and `auditability-0/1/2.md`); the value/auditability rubrics,
pointed to only as a directory (`references`, lines 32-36, rather than the actual files
`resources/jev/value.md`, `auditability.md`, `contribution.md`, `usefulness.md`,
`relevance.md`); "moderator" (line 131, and `resources/jev/auditability.md`);
"true-means-pass statement" (line 91); "Python's chassis" (line 91; the earlier Python
implementation in the `archaeology` layer); and "no TRUE/FALSE criteria and no field names"
(line 117).

Two nuances worth adding so the fix is precise rather than mechanical:
- "no TRUE/FALSE criteria and no field names" is not a contradiction to be resolved — it
  describes the **three gate question texts** (`resources/jev/contribution.md`,
  `usefulness.md`, `relevance.md`), which are the owner's plain questions verbatim with no
  appended true/false rubric and no field labels; the score questions legitimately reference
  `` `new_message` `` and the code uses short keys (`jev.rs:43-53`). Wording should say
  this so a reader does not think the code violates the decision.
- `ask()` accepts any `f64` in `0..=5` (`jev.rs:168-171`), so "score band" needs a stated
  bucketing rule for fractional scores, not just the integer levels 0/1/2. `prompts.rs`
  owns that mapping; the description should either state it or point to the file.

**What should change (description).** Add a short "Definitions" section (or inline
expansions) covering JEV, the prefix, score bands (with the ≥ 3.0 pass rule and the
fractional-bucketing note), the named rubric files, moderator, true-means-pass statement,
Python's chassis, and the "no TRUE/FALSE criteria and no field names" clarification; link
or remove "Jev's documentation". No code change, though the fractional-score bucketing is
worth confirming in `prompts.rs`.

---

## GF11 — Nit — `superseded` layer — **Right**

**Why.** Two entries are marked superseded without saying what replaced them, and one of
them is not actually superseded:
- line 154 "Evaluation happens once, before distribution" — still current (GF6).
- line 150 "The three judgments may be requested in one inference" — the *three* is
  superseded (now five checks), but **one request/inference** is still exactly current
  (`rules[0]`, `jev.rs:55-59`, `turn.rs:159-180`). Marking the whole sentence superseded
  hides a live invariant.
The genuinely superseded entries are lines 142 and 146 (three conditions / all three at
70%), replaced by the five-check rule (`rules[0]`, `rules[2]`).

**What should change (description).** Keep only lines 142/146 in `superseded`, each with a
"superseded by" pointer to `rules[0]`/`rules[2]`; move "one request/inference" into the
current rules as an explicit invariant; delete line 154 from `superseded` (or annotate it
"still current, not superseded"). This also closes GF6's first half.

---

## GF12 — Nit — `elephant` gap wording — **Right, with one nuance**

**Why.** The gap (line 189) "JEV requests are not saved in the table record, so a decision
can only be rebuilt afterwards" is genuinely unclear: it does not say *what* is not saved
(the state + questions + answers), *who* rebuilds it, or from what (the log), and "rebuilt
afterwards" reads as if the decision were reproducible when in fact it is only
*approximately reconstructable*. The second half of the finding — that it "sits awkwardly
with the auditability goal" — is a **wording collision rather than a logical conflict**:
the `auditability` *score* (line 131, `resources/jev/auditability.md`) judges whether a
**participant's contribution** is inspectable from the messages, whereas this gap is about
**JEV's own verdict** not being directly auditable. They are distinct concerns that happen
to share the word. Still, the project's broader stated value is that "the roundtable
[is] actually able to be read and understood" (line 132), so a gate whose inputs are not
recorded is a fair, if minor, awkwardness to record.

**What should change (description).** Reword the gap to: "JEV requests (state, questions and
numeric answers) are not persisted in the table record, so a verdict cannot be replayed or
audited directly; it can only be reconstructed approximately from the log, and the token
estimate means the reconstructed state may differ." Optionally note the fix: persisting the
JEV request/response per `ticket` would close both this gap and make the `RT-G01` gate
auditable. A **code** change (saving the request/response) is the more valuable resolution;
if it is out of scope, the reword is the minimum.

---

## Cross-cutting conclusion

The findings are not twelve independent defects. They describe one stale-documentation
problem plus a small number of real code/comment issues:

1. **Root cause (GF1, GF2, GF3, GF4, GF6, GF7, GF8, GF9, GF11):** the `wants`, the
   `reasons` / `judging context` / `JEV is optional` decisions, `rules[5]` and the
   `superseded` layer still describe the superseded three-condition design (three 70%
   conditions, JEV prose reasons, truncation, short deadline, never waits, objective in
   state, window as a setting). The code implements the 7 Nov 2026 owner spec: five checks
   in one request, numeric answers, author feedback from fixed files, `topic`/`conversation`
   (4 rounds)/`new_message`, two constant token limits, no timer, RT-G10 floor wait. Fix
   the description once, consistently, rather than per finding.
2. **Missing documented behaviour (GF5, GF8, GF10):** chair guidance in `conversation`,
   state-too-big handling, turn-start topic capture, malformed-answer errors, after-work
   non-blocking, the meaning of the two token constants, `topic` when topics are off, and
   the glossary of owner terms. Add these; no code change.
3. **Genuine code-side items (flag for the owning element, do not resolve by wording
   alone):**
   - `turn.rs:124` stale "Truncate" doc comment and `turn.rs:2` "never holds the table"
     comment (GF3/GF6/GF9).
   - No JEV timeout (`jev.rs:3`, owner-attributed) versus the decision's "short deadline"
     and the owner's "never halts" intent; with RT-G10 a silent JEV can stall the table
     (GF3/GF9). Add a timeout or explicitly record the deviation.
   - `gates` layer omits RT-G10 (and RT-G02), though `submit` implements both (GF9).
   - Fractional score values (`jev.rs:168-171` accepts any `f64` in 0..5) need a stated
     score-band bucketing rule (GF10).
   - Persisting JEV requests/responses would close the `elephant` gap (GF12).

Nothing in the review is a false positive; I recommend accepting all twelve and applying
the consolidated description edit above, with the five code-side items tracked separately.

---

## Reconciliation — corrections adopted after roundtable review (RiskySaber, final round)

The per-finding verdicts above (all twelve right) stand, but three resolutions and three
scope notes were revised after MoltedFleet, WindyNexus, KineticNeutron and ActiveFalcon
challenged them. This section is authoritative where it differs from the draft above.

### GF3 / GF9 — the floor-wait is a code-vs-owner conflict, not stale prose (draft was wrong)

My draft resolved the contradiction by *describing* the wait and marking the owner's
"the table never waits on JEV" as effectively superseded. That is the wrong fix. Evidence:

- Owner decision (`element.md:109-110`, by `owner`, 2026-11-05): "If JEV is down this
  doesn't halt, it continues... Halting can prove more expensive than not." Decision body:
  "No blocking retries, and **the table never waits on JEV**."
- Code: `submit` sets `judging_floor = Some(ticket)` for non-after-work replies
  (`turn.rs:170-173`, RT-G10); `resolve_reply` returns `None` instead of an `Outcome` for
  that contribution (`turn.rs:112-115`); the barrier clears only in `on_judged`
  (`turn.rs:186-189`). The next floor turn therefore waits for the verdict.

The owner is the source of truth; a recent, rationale-laden owner decision cannot be
reversed by editing a functional-map description to match an implementation. **Resolution:
escalate.** Either (a) the owner confirms the wait (then the owner decision must be
formally superseded, with a dated reversal), or (b) the code is fixed to release the floor
(preferred, restores "never waits"). Until decided, the description must **state the
conflict and preserve the requirement**, not enshrine the wait. Do not mark "never waits" as
superseded without authority.

The code option is *not* a one-line flag deletion (WindyNexus, MoltedFleet): the barrier is
coupled to opportunity accounting. `opportunity(...)` is called exactly once, in
`on_judged`'s `count` closure (`turn.rs:191-197`); there is no submission-time call site.
Removing `judging_floor` alone leaves `resolve_reply` still returning `None` (it also
checks `!after_work`) and, if `floor` becomes `false`, a *rejected* floor turn would lose
its opportunity entirely (`else if accepted` never counts on rejection). A safe fix must,
together: (1) stop setting `judging_floor` in `submit`; (2) drop the `None` early return in
`resolve_reply` and count the opportunity exactly once there (e.g.
`self.opportunity(Some(Outcome::Contributed))`); (3) make `on_judged`'s accept branch only
`record_accept()`, never `opportunity(...)`, for former floor turns; (4) reword RT-G10
("verdicts may arrive after the floor turn; opportunity counted at submission"). See
`WindyNexus-floor-fix.md` and `MoltedFleet-floor-fix-correction.md` for the full accounting
argument. Alternative lower-risk option (ActiveFalcon): bound the whole JEV call with a
timer and route expiry through the existing `Err` handler (`turn.rs:199-203`), which
already removes the pending judgement, clears the barrier, accepts unjudged and counts the
opportunity — this honours the recorded "short deadline" without changing accounting. Zero
added floor latency requires the full decouple; a bounded call does not. Both are specified;
neither is an implementation claim.

### GF2 — scope narrowed; two evidence corrections (draft overstated)

My draft said "no code change needed" and treated the decision as authoritative. Corrections:

- **Attribution (ActiveFalcon):** the `confidence`/`reasons` decision is `by: Claude`
  (`element.md:87-98`), **not** by the owner. `rules[3]` (line 46) is the owner-side rule
  and specifies fixed feedback. So GF2 is a **description reconciliation between a Claude
  decision and the owner's rule**, not a case of an owner promise that must be withdrawn.
  Fix: align the decision with `rules[3]` (as the draft already proposes), and say so.
- **Verification (ActiveFalcon):** `prompts::rejected(&failed)` receives
  `failed: Vec<(String, f64)>` — i.e. the numbers are passed in (`turn.rs:209-216`). A
  formatter can append a number to a fixed template without a numeric placeholder, so the
  absent `prompts.rs` means the copied source does **not** independently prove the author
  notice omits confidences. The review finding (`prompts.rs:44-54`, "- Label: <owner
  feedback>") is accepted as reported but must be labelled **not independently verified
  here**. By contrast, the floor-Outcome withholding (GF3/GF9) is directly visible in
  `resolve_reply` and needs no absent file — the load-bearing finding is unaffected.
- Practical consequence: GF2 belongs in the **description-only** bucket (reconcile the
  Claude decision with `rules[3]`); if the author notice truly omits the number and the
  owner wants it shown, that is a follow-up code change, not a reviewer ruling.

### GF8 / GF10 / GF12 — narrowed fixes

- **GF8:** "make the limits explicit" must include their *reason*: 32,000
  (`STATE_PLUS_QUESTION_TOKENS`) = state + the longest single question (so any one gate
  fits); 64,000 (`REQUEST_TOKENS`) = state + the whole five-question request
  (`jev.rs:63-66`, `jev.rs:89-96`). Without the reason a reader may merge them again.
- **GF10:** partly unfair as drafted. The `references` directory pointer does locate the
  rubrics; what is missing is a one-line summary of each 0-5 scale, plus **cite or drop**
  the unsourced "Jev's documentation says accuracy falls as irrelevant state grows"
  (`element.md:103`) — it is used to justify the window but has no source in the map. Keep
  the glossary for the genuinely undefined terms.
- **GF12:** state it precisely — in `on_judged` the `Judgement` is removed after use
  (`turn.rs:185`), only `scores` and failed-check strings survive, and the sent `state`
  is never persisted. Say "**outcome inspectable, inputs not re-derivable**". Drop the
  overstated "tension with the auditability goal": that score rates the *author's message*
  (`resources/jev/auditability.md`), not JEV's inputs; the two are distinct.

### Final split

- **Description-only:** GF1, GF2 (reconcile Claude decision ↔ `rules[3]`), GF4, GF5,
  GF6, GF7, GF8 (with reasons), GF10 (with cite-or-drop), GF11, GF12 (precise reword).
- **Owner/code conflict — escalate, do not resolve by prose:** GF3, GF9.
- All twelve findings remain **right**; no false positives. The `prompts.rs`/`engine.rs`
  absence weakens only the *exact rendering* claim in GF2 and GF1's "reasons" source
  detail, not any verdict.

### Verification note on the absent files

The copied `source/` lacks `prompts.rs`, `engine.rs`, `rules.rs` and the gate registry.
GF2 and GF3/GF9 do **not** depend on them: `turn.rs:112-115`, `turn.rs:170-173`,
`turn.rs:209-216`, `turn.rs:225` plus the `resources/feedback/` files establish the
floor-wait, the author/event split, and the fixed-feedback content. So the load-bearing
findings are fully auditable from the snapshot; only `prompts.rs`'s exact string rendering
is taken on the reviewers' report.

