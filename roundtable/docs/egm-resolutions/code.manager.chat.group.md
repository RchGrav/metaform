# Resolution of review findings — `code.manager.chat.group` (Roundtable)

Reviewed by DirectOmega, with final evidence qualifications by LethalSaturn. All twelve
findings identify description issues, subject to the source limitations below. The
primary remedy is to update `element.md`; this does not establish that every missing-file
subclaim is correct or that the implementation has no defects. The map mixes historical
decisions with a newer, owner-directed design.

## Verification basis and caveat

- Files present in `source/`: `engine.rs` (997 lines) and `rules.rs` (175 lines) only.
- `engine.rs` is the same file the reviewers cited: every engine.rs line number in the
  findings (6-8, 12, 397, 499-500, 504-507, 510-513, 541-552, 554-556, 636-640,
  647-651, 666-681, 789-792, 901-907) resolves to the behaviour the finding describes.
  `rules.rs` citations (50-59, 54, 107-110) likewise check out.
- **`turn.rs`, `config.rs`, `jev.rs`, `prompts.rs`, `events.rs` are cited by the findings but
  are not in `source/`.** Claims that depend only on those files (GF3 `turn.rs:170-173`,
  `jev.rs:3`; GF4 `config.rs:164`, `turn.rs:516-549`; GF6 `turn.rs:205-210`, `turn.rs:422-425`)
  cannot be *directly* confirmed here. They are nevertheless accepted as right because they
  are consistent with (a) the engine.rs/rules.rs code that is present, (b) the description's
  own `rules`/`gates`/`elephant.built` layers, and (c) the roundtable evaluation model
  (three 0.7 true/false gates plus two 0–5 scores at ≥3) that this exercise itself describes.
  `engine.rs` calls but does not define `start_rating`, `resolve_reply`, `commit`,
  `turn_prompt`, `on_judged`, `on_rating`, `on_proposal`, `change_topic`, `start_polling`,
  `finish_polling`, `settle_poll`, `settle_results`, `ask_to_rate`, `rating_done`,
  `on_scored` — these live in the absent `turn.rs`, confirming the source is a partial copy.

## Root cause (one issue behind GF1–GF4, GF7, GF8)

`element.md` mixes two generations of the design without a precedence marker:

- **2026-11-05 `decisions`** (and the 11-05 `owner_statements` consequence at line 113):
  WORK first-line reply, a deliberation window with +512 skip credits, "no automatic end /
  no rankings / runs until the chair ends it", topic progression by default.
- **2026-11-07 owner direction** (`owner_statements` lines 137-142: "make it by default 10
  rounds", "unlimited must have some kind of end"; `rules` lines 172-174; `gates`
  RT-G03/04/05/06/10; `elephant.built` line 236): 10 rounds then a rating round, topics
  off by default, waits for two free agents and for JEV, no timers, no skip credits, work
  detected from ACP tool activity.

The code header states the newer owner decisions directly: engine.rs:7 quotes the owner
"Saying work, thats not a thing" and engine.rs:12 records "No timers anywhere (O)". So the
11-05 decisions were deliberately replaced. The fix is to **annotate the stale layers as
superseded and correct their text**, not to rewrite working code to resurrect decisions the
owner abandoned. This also answers GF7 ("nothing says which statement wins").

A second, separate rule applies: the owner said "As a general rule I don't add extra logic
and gates" (owner_statements line 132-133) and engine.rs:12 forbids timers. Therefore the
unbounded waits highlighted by GF3/GF8 must **not** be "fixed" with new code/timeouts; they
are owner-designed gates (RT-G03 "owner-designed", RT-G10 "owner disposition pending"). The
description should state them honestly and the residual stall risk should be put to the owner.

## Summary

| Finding | Right? | Change | Where |
|---|---|---|---|
| GF1 | Right | Description: supersede WORK decision; correct PASS wording | `decisions` signalling (72-77) |
| GF2 | Right | Description: supersede deliberation-window decision; drop +512 credits; correct line 113 | `decisions` (78-84), `owner_statements` (113) |
| GF3 | Right | Description: correct "nothing waits / only pause" clauses; name the three waits | `owner_statements` (113) |
| GF4 | Right | Description: supersede "no automatic end / no rankings" decision; state current ending + rating round | `decisions` ending (93-97) |
| GF5 | Right | Description: expand no-limit ending rule with the topics/poll precedence and "end = rating round" | `rules[0]` (172), `gates` RT-G06/RT-G08 |
| GF6 | Right | Description: fix "three 70%", fix quota wording, document five behaviours | `wants` (24, 27) + new behaviour subsection |
| GF7 | Right | Description: add superseded markers / precedence statement | `decisions` layer header |
| GF8 | Right | Description: document the two-free wait, its clearing, its unboundedness; reconcile with "don't get stuck"; flag to owner | `rules[1]` (173), `gates` RT-G03, `investigations` |
| GF9 | Right | Description: state precedence when topics on + no round limit | `rules[0]`, `gates` RT-G06/RT-G08 |
| GF10 | Right | Description: add glossary / define on first use (esp. JEV); footnote archaeology-only terms | opening + new glossary layer |
| GF11 | Right | Description: state what `advance` does with topics off (and during a poll) | `wants` line 17 |
| GF12 | Right | Description: legend note, update/close idle-loop investigation, cite or drop "500-line limit" | Properties, `investigations`, `elephant.gaps` |

---

## Per-finding decisions

### GF1 — Blocker — WORK convention — **RIGHT**

**Verification.** `decisions` (element.md:72-77) says "A reply whose first line is WORK
declares independent work" and the `safety` line refers to "No WORK, PASS or occupancy
rule". The code has the opposite design. engine.rs:6-8: "An agent is working when ACP
reports tool activity during its turn; **it is not asked to announce work** (O: 'Saying
work, thats not a thing'; D §6)". Work is detected by `on_tool` (engine.rs:666-681): a
`ToolActivity` on a `Floor(prompt)` moves the seat to `Working(prompt)`, sets
`worked_in_topic`, releases the floor, publishes `WorkStarted`, and records
`Outcome::SkippedWorking`. `rules::classify` (rules.rs:50-59) knows only `Empty`, `Pass`,
`Contribution` — no `Work` variant. PASS is `trim_end_matches('.').eq_ignore_ascii_case("pass")`
(rules.rs:54): case-insensitive, trailing dots allowed.

**What should change (description).** Mark `decisions` "signalling contribute / pass / work"
as **superseded (2026-11-07)** and replace it with the code's actual convention: work is
inferred from ACP tool activity / background reports, never from a reply token; `classify`
has exactly three outcomes. Also correct the surviving "exactly PASS" wording (line 75):
code accepts case-insensitive `pass` with trailing dots. Keep the true safety statement
that no rule cancels an ACP turn (engine.rs never calls `session/cancel`; shutdown only in
`end`, engine.rs:930-940).

**Why.** The map must describe what the program does. The code cites a *later* owner quote
than the 11-05 decision, so the decision is abandoned, not a code defect.

---

### GF2 — Blocker — deliberation window / +512 credits — **RIGHT**

**Verification.** `decisions` "deliberation window" (element.md:78-84) describes a
configurable window after which a silent agent is "treated as occupied", "earns +512 per
skipped opportunity", and `owner_statements` line 113 repeats "a silent participant is
treated as occupied after the deliberation window". engine.rs:12 is explicit: "**No timers
anywhere** (O)". There is no timer, no window, no `+512` credit anywhere: the only `512`
constants are `DEFAULT_BASE` (a character limit, rules.rs:8) and `PROPOSAL_LIMIT`
(rules.rs:19); `session_points` (engine.rs:168) is peer-rating points, not skip credits.
Instead of a timeout, busy agents are skipped *immediately* from ACP activity
(engine.rs:570-576, 666-681) and `waiting_for_free` is cleared by events
(prompt completion 690, background-work end 475-478, seat ready 829, fail 737, exit 768).

**What should change (description).** Mark the deliberation-window decision **superseded**;
delete the "+512 per skipped opportunity" credit and the "silent participant treated as
occupied after the window" clause from `owner_statements` line 113. Replace with: no timers;
a busy/occupied agent's turn is skipped at once and never cancelled, its next discussion
prompt gets the recovery allowance once (engine.rs:570-575, 396-399); a hung provider is
observed as `PromptFailed`/`HarnessExited`, recorded, and the table continues.

**Why.** Same generation gap as GF1, and engine.rs:12 is an explicit owner decision. Adding
a timer to match the description would violate it.

---

### GF3 — Blocker — "nothing waits on an optional service" — **RIGHT**

**Verification.** `owner_statements` line 113: "Nothing in the loop waits on a person or on
an optional service ... **The only pause is an explicit chair hold**." The code has three
waits, all owner-designed:

1. **JEV verdict** — engine.rs:510-513 `step()` returns while `floor` or `judging_floor` is
   `Some`; the field comment (engine.rs:160-164) says "the next turn waits for its answer".
   Gate RT-G10 "The next turn waits for JEV's verdict" is listed as active. engine.rs:845
   dispatches `Internal::Judged` to the missing `on_judged` handler; it does not visibly
   clear the flag or prove this is the only clearing path. Importantly, that event carries
   a `Result<BTreeMap<String, f64>, String>` (134–137): transport errors can arrive as
   internal events, and the missing handler may release the wait and fail open on them.
   The engine supplies no deadline, but missing service code prevents establishing the
   complete request's timeout. The explicit scheduling wait alone contradicts the
   description's unconditional no-wait claim.
   **Verified / unverified split (auditability):** verified — the named scheduling wait
   gated on `judging_floor`, without an engine deadline (engine.rs:510-513, 845, 12); *unverified* — whether
   `judging_floor` is set when JEV is unreachable-with-a-key, and whether a transport error
   fails open on that path (both live in `turn.rs`/`jev.rs`, absent from `source/`). So
   "a down JEV halts the table" and "a JEV error fails open" are **hypotheses to test once
   `turn.rs` is copied in**, not established facts. Owner statement line 117 ("if JEV is down
   this doesn't halt") and consequence line 118 ("optional services fail open") make this a
   potential code defect on the down-path, but its severity is conditional on the absent file.
2. **Fewer than two free** — engine.rs:541-552 (`MIN_FREE_TO_DISCUSS = 2`, line 30): sets
   `waiting_for_free = true` and returns; gate RT-G03.
3. **Topic poll** — engine.rs:503-508: while polling, `step()` returns unless
   `waiting`/`pending` are empty; comment "a topic poll waits for every agent"; lines
   127-128 and 677-678 confirm the poll waits for busy proposers. The reviewers cite
   `turn.rs:170-173` / `jev.rs:3` (absent) for the JEV no-timeout detail; engine.rs:511-513
   is the visible part and is consistent.

**What should change (description).** Correct the two false clauses in `owner_statements`
line 113. Keep the true clauses (permission requests answered automatically, JEV *failure*
lets contributions through unjudged, provider failures recorded and the table continues).
Add: the next turn waits for JEV's verdict, the table waits while fewer than two agents are
free, and a topic poll waits for every agent; JEV *failure* behaviour on the floor path is
governed by `turn.rs` (not in `source/`) and must be confirmed before any claim that it
fails open or halts. Clarify "the only pause is an explicit chair hold" → "the only
*user-initiated* pause is an explicit chair hold". Note the gates are owner-designed /
owner-disposition-pending, so no code change in `engine.rs`/`rules.rs`; record the
down-path JEV question as an owner disposition plus a request to copy `turn.rs` into
`source/` so GF3's severity can be decided, rather than asserting it now.

**Why.** These waits are already listed in the `gates` layer (RT-G03, RT-G10), so the
document contradicts itself; line 113 is the stale overclaim.

---

### GF4 — Blocker — "no automatic end / no rankings" — **RIGHT**

**Verification.** `decisions` "ending" (element.md:93-97): "A Roundtable has **no automatic
end**: no topic count ... **It runs until the chair ends it**. Python's ... **rankings** and
reporter are not carried over." Code: engine.rs:636-640 ends after `cfg.rounds` (default 10,
`rules.rs:12 DEFAULT_ROUNDS`, `config.rs:164` per the finding) and starts the rating round;
engine.rs:647-651 ends after two quiet rounds with no limit; `Table` has `ranking:
Option<String>` and `session_points` (engine.rs:168-170), `start_rating()` is called at
639/650/906, and `settle_results` is called on every prompt end (711, 755, 787). The
reviewers cite `turn.rs:516-549` for the built session ranking (absent), but the fields and
call sites in engine.rs confirm the feature. `elephant.built` (line 236) already says
"ends after the set rounds and runs the rating round".

**What should change (description).** Mark the "ending" decision **superseded**. Replace
with: a table runs its configured rounds (10 by default) and then a rating round; with no
round limit it ends when two consecutive rounds bring no accepted message (or starts a topic
poll when topics are on, see GF5/GF9); the chair's `End` starts the rating round, and a
second `End` (or `End` during rating) shuts down. Reword "no rankings": the current build
*does* collect peer ratings and build a session ranking/ranking message — what was dropped
was Python's synthesizer/reporter/rankings phase, not the owner's rating round.

**Why.** The 11-07 owner statements ("10 rounds by default", "unlimited must have some kind
of end") explicitly mandate this ending; the elephant layer already records it as built.

---

### GF5 — Major — no-limit ending scope / precedence — **RIGHT**

**Verification.** engine.rs:647: the no-limit end fires only when
`advance && cfg.rounds.is_none() && (!topics_active() || !topic_had_input())`. Otherwise
(654-656) `advance && topics_active()` sets `topic_due = true` → `start_polling()` (520-522).
So with topics on and the topic having had input, two quiet rounds start a **poll**, not an
end. rules.rs:102-110 `close_round()` returns true at `nonproductive_streak >= 2` **or**
`all_pass_streak >= 2`; `passed` counts `Passed | SkippedWorking` (rules.rs:91), so rounds of
all passes or busy skips do count as quiet. Note `nonproductive_streak` increments whenever
`accepted == 0` (rules.rs:106) regardless of outcome, so an **all-failed round** also counts
— broader than the finding's "all passes or busy skips"; the corrected rule text must say
"two consecutive rounds with no accepted message," not "two rounds of passes/skips". The
"end" is `start_rating()` (650) — the rating round begins; shutdown happens later
(engine.rs:901-907, 930-940).

**What should change (description).** Expand `rules[0]` (line 172). State: "two rounds with
no accepted message" = two consecutive rounds with `accepted == 0` (any mix of passes,
busy skips, or failed turns — rules.rs:102-110), *or* two consecutive all-pass/skip rounds; the no-limit end applies when topics are off **or** the current topic had
no accepted message/file work; otherwise two quiet rounds start a topic poll; "end" means the
rating round starts (the table shuts down after rating). Add cross-references to gates
RT-G06 and RT-G08.

**Why.** The one-line rule hides a real branch; a reader cannot predict behaviour with
topics on and no round limit.

---

### GF6 — Major — wants mismatches / undocumented logic — **RIGHT**

**Verification (sub-point by sub-point).**

- "three 70% conditions" (wants line 24) vs five checks: rules.rs:15 `GATE_PASS = 0.70`,
  rules.rs:17 `SCORE_PASS = 3.0`. The evaluation model (this exercise's own framing) is
  three 0.7 true/false gates **plus** two 0–5 scores at ≥3. The reviewers cite
  `turn.rs:205-210` (absent) for the five checks; consistent with the constants present.
  The want wording is incomplete.
- Quota (wants line 27 "none by default; 1,024 once after a busy skip"): `limit_for`
  (engine.rs:396-399) is `let base = self.cfg.base_allowance?; Some(if recovery_due {
  recovery_allowance } else { base })`. The `?` means **when there is no base limit there is
  no limit at all, including no 1,024 recovery** — recovery is relative to a set base. The
  want's claim is false for the default (no-limit) case.
- Undocumented, all confirmed in engine.rs: two-step `End` (901-907: first starts rating,
  second/within-rating shuts down); "turns start only once every seat has started" (499-500,
  `seating` guard); "ends when no seats left" (789-792, and 838-841 "no participant could
  start"); "review notice once per waiting episode" — the guard `!told_to_review` (543),
  set true in `ask_to_review` (586), reset once ≥2 are free (554-556); "rating needs at least
  two named seats" (`turn.rs:422-425`, absent — accepted on consistency with engine.rs
  `rating`/`names()` and the owner's "need at least two agents to have a debate").

**What should change (description).** (1) Reword the gate want from "three 70% conditions"
to the actual check set (three 0.7 gates + two ≥3 scores) and cross-reference
`GATE_PASS`/`SCORE_PASS`. (2) Reword the quota want: with no base limit there is no limit and
no recovery allowance; the 1,024 recovery applies only once, after a busy skip, *when a base
limit is set*. (3) Add a short "Control commands, startup and shutdown" subsection
documenting the five behaviours above (with their engine.rs line anchors).

**Why.** These are real behaviours a maintainer/reader would otherwise miss, and two want
lines are factually inaccurate. No code change is warranted: the behaviours are
intentional (owner-designed gates; engine.rs comments cite owner decisions).

---

### GF7 — Major — decisions vs rules, no superseded layer — **RIGHT**

**Verification.** Directly from the document: `decisions` "ending" (95-96) "no automatic
end, no rankings, runs until the chair ends it" vs `rules[0]` (172) "10 rounds by default,
then the rating round"; `decisions` "deliberation window" (83) "+512 per skipped
opportunity" though no credit exists; `decisions` "rounds" (88-90) topic progression though
`topics` is off by default (config.rs:164 per GF4; engine.rs:374-379 `topics_active` requires
`cfg.topics && judging && jev.configured()`). There is no `superseded`, `deprecated`, or
precedence layer; `decisions` entries carry only a `date` (2026-11-05) and one has
`status: "decided, flagged for owner review"`. The `elephant` layer (229-240) describes the
current build but does not say it overrides `decisions`.

**What should change (description).** Add an explicit precedence statement at the top of
the `decisions` layer: "Entries dated 2026-11-05 record an earlier design. Where they
conflict with `rules`, `gates`, `elephant.built`, or `owner_statements` dated 2026-11-07,
the latter are authoritative for current behaviour." Mark the four affected decisions
(signalling, deliberation window, rounds, ending) `status: "superseded 2026-11-07"` with a
one-line pointer to the replacement rule/gate. (This is the single edit that resolves the
"which wins" question for GF1–GF4 and GF8 together.)

**Why.** A functional map that simultaneously asserts X and not-X, with no precedence rule,
is not usable as a specification.

---

### GF8 — Major — two-free wait vs "don't get stuck" — **RIGHT**

**Verification.** `rules[1]` (173) "The table waits while fewer than two agents are free"
vs `owner_statements` (112-113) "This roundtable must do everything it can not to get
stuck" and "The only pause is an explicit chair hold". engine.rs:541-552 sets
`waiting_for_free = true` with **no timer** (engine.rs:12); it is cleared only by events
(690, 475-478, 829, 737, 768). If every agent stays busy/working, `free.len() == 0`, the
`[lone]` branch (542) does not fire, no notice is emitted, and the table waits
indefinitely — `rules[1]`'s "a lone free agent is told once to review" does not cover the
all-busy case, and nothing in the description says what happens then. Gate RT-G03 is
"active, owner-designed", so this is intentional, not a bug.

**What should change (description).** In `rules[1]` / gate RT-G03: document that the wait
is cleared on prompt completion, background-work ending, a seat becoming ready, a failed
turn, or a harness exit; that there is no bound (no timers, owner decision); and what
happens when all agents are busy (the table simply waits; no review/alone notice because
there is no lone free agent). Reconcile with the "don't get stuck" owner statement: that
principle is served by fail-open JEV/provider handling and by skipping busy agents, with
RT-G03 as an explicit owner-designed exception. **Add an `investigations` item (or a note
on RT-G10/RT-G03, which are "owner disposition pending") flagging the residual
all-busy/hung-JEV stall to the owner.** Do not add a timeout in code: engine.rs:12 and
owner_statements line 132-133 forbid new timers/gates without an owner decision.

**Why.** The contradiction is real and the unbounded case is a genuine operational risk; but
the resolution belongs in the description and in an owner disposition, not in new code.

---

### GF9 — Major — two-quiet-rounds precedence unstated — **RIGHT**

**Verification.** `rules[0]` (172) "With no round limit it ends when two rounds bring no
accepted message"; gate RT-G06 "ends when there is no more good input"; `code.selector.topic`
want (30) and gate RT-G08 (engine.rs:653-656) "two quiet rounds start a topic poll". The
description never states which wins when topics are on **and** there is no round limit. Code
does resolve it (engine.rs:647 `!topic_had_input()` → end; else 654-656 → poll), as detailed
in GF5, but the description does not.

**What should change (description).** In `rules[0]` and the RT-G06/RT-G08 gate notes, state
the precedence: with no round limit and two quiet rounds, the table ends when topics are off
or the current topic had no accepted message/file work; when topics are on and the topic had
input, it starts a topic poll instead. Cross-reference engine.rs:647.

**Why.** Removes an ambiguity that GF5 shows is already resolved in code; the map should
match.

---

### GF10 — Major — undefined project terms — **RIGHT**

**Verification.** All the listed terms appear in `element.md` with no definition: JEV (the
opening at line 3 says only "an evaluator"; JEV is used from line 24 onward), ACP v1/v2
`stopReason`/`state_update`/`session/cancel` (line 75), chair (17-18), seat (29), harness
(29), head of the table (17, 132), rating round (172, 236), AgentSight (118, 101),
Python/archaeology (68-69, 90, 96), PV correction turn (89), run 1 T755 (102), M2/M3/M4
(163). A reviewer new to the project cannot read these.

**What should change (description).** Add a short glossary layer (or inline first-use
definitions). At minimum: define **JEV** on first use (the opening should name it, not just
"an evaluator"); define ACP and the v1/v2 activity signals, chair/seat/harness/head of the
table, rating round, and AgentSight. For archaeology-only references (Python runner,
`archaeology/` paths, PV correction turn, run 1 T755, M2/M3/M4), either give a one-line
gloss or move them to a "historical references" note — they are provenance, not part of
what the current part does. Note this is partly map-wide (the same metadata/terms appear in
every element), so a shared glossary is preferable to per-element duplication.

**Why.** Comprehension blocker for the stated audience (reviewers who had never seen the
project). No code change.

---

### GF11 — Major — `advance` with topics off — **RIGHT**

**Verification.** `wants` line 17: `code.server.tool` "Function: Ends the current topic and
starts the next one, either with a topic chosen by the caller or **through the normal poll**".
Topics are off by default (GF4; engine.rs:374-379; `owner`/`config`). What `advance` does
when topics are off is not stated in the description. Code defines it: engine.rs:873-880 —
`!topics_active()` → error notice "topics need JEV (judging on and a key)"; polling in
progress → error notice "the poll decides"; otherwise queue the advance. `step()` only
applies it `filter(|_| self.topics_active())` (514). `TableHandle::topics_enabled()` (213-216)
and `flags.topics` (272) confirm topics need `cfg.topics && judging && jev.configured()`.

**What should change (description).** Add to the `code.server.tool` want (or a new command
note): with topics off (the default) `advance` is refused with an error notice and nothing
changes; it is also refused during a topic poll; it only sets/polls a topic when topics are
active (judging on and a JEV key). Cross-reference gates RT-G11 (engine.rs:872) and the
"topics require JEV" owner decision.

**Why.** The want describes a path that is unreachable by default; a reader would assume
`advance` always works. No code change.

---

### GF12 — Nit — Properties metadata, stale investigation, unsourced limit — **RIGHT**

**Verification.** (1) `Properties` (7-13): `role: "DE"`, `name_length: 3`, `name:
"Roundtable"`, `package`, and the `Intent` values (`send`, `send_receive`, `receive`) are
unexplained in this document ("applies to all elements" — they are map-wide conventions).
(2) `investigations` "OPEN - idle loop cost" (150-152) describes ~1,590 topic cycles when
every seat passes; with topics off by default and 10 rounds by default (11-07) that specific
runaway is mitigated, and the built warning notice is now partly moot — the item is stale.
(3) `elephant.gaps` (239) "over the 500-line limit" has no source anywhere in `element.md`
(engine.rs is 997 lines; rules.rs 175).

**What should change (description).** (1) Add a one-line legend note that these fields are
map-wide conventions defined at the map level (or define them here); since it applies to all
elements, flag it as a map-level action rather than an element-local rewrite. (2) Update or
close the idle-loop investigation: record that topics off by default + 10-round default
mitigate the 1,590-cycle case, and that the open question ("should the table hold itself
when idle") is now bounded by the round limit / no-limit two-quiet-round ending — keep only
the genuinely open part (all-busy stall, see GF8) and point to the owner. (3) Either cite
the source of the 500-line limit or drop the claim from `elephant.gaps`; if kept, note
engine.rs is ~997 lines.

**Why.** Small accuracy/completeness fixes; no code change.

---

## Consolidated edit list for `element.md`

1. Add a **precedence/superseded note** to the `decisions` layer; mark the signalling,
   deliberation-window, rounds, and ending decisions `status: superseded 2026-11-07` (GF1,
   GF2, GF4, GF7).
2. Rewrite `owner_statements` consequence line 113: drop the deliberation window / credits;
   replace "nothing waits on an optional service" and "the only pause is an explicit chair
   hold" with the three real waits (JEV verdict, two-free, poll) and "only *user-initiated*
   pause" (GF2, GF3, GF8).
3. Replace the stale `decisions` WORK/ending text with the code's actual conventions
   (work from ACP tool activity; 10 rounds + rating round; no-limit two-quiet-round end)
   (GF1, GF4).
4. Expand `rules[0]`/`rules[1]` and the RT-G06/RT-G08/RT-G03 gate notes with the precedence,
   the all-pass/skip counting, the "end = rating round", the wait-clearing events, and the
   all-busy case (GF5, GF8, GF9).
5. Fix `wants` line 24 ("three 70% conditions" → three 0.7 gates + two ≥3 scores), line 27
   (no-limit → no recovery allowance), and line 17 (`advance` with topics off / during a
   poll) (GF6, GF11).
6. Add a **"Control commands, startup and shutdown"** subsection documenting two-step End,
   seating guard, no-seats-left end, ≥2 named seats for rating, and once-per-episode review
   notice (GF6).
7. Add a **glossary** (JEV first) and footnote/move archaeology-only terms (GF10).
8. Add a **Properties legend note**, update/close the idle-loop investigation, and cite or
   drop the "500-line limit" (GF12).
9. Add an `investigations`/gate note flagging the **residual all-busy / hung-JEV stall** to
   the owner, explicitly *without* proposing new timers/gates in code (GF3, GF8).

**No new timers or WORK/credit mechanisms are recommended.** Most findings are description
defects. Two small code cleanups are justified by visible source: change the misleading
“Exactly PASS” comment (`rules.rs:43`) to describe the permissive classifier, and make the
inactive-Advance error (`engine.rs:875`) mention enabling topics as well as judging/key.
The missing JEV handler still needs checking: setting `judging_floor` during a request
does not prove a bug; failure to release it and fail open after a reported transport error
would violate the existing owner requirement. That requirement needs no new owner decision.
Where a gate is
"owner disposition pending" (RT-G06, RT-G10, RT-G14, RT-G16), the description should say so
rather than silently assert a behaviour.

Clearing `waiting_for_free` also only triggers another availability check, rather than
guaranteeing progress. Completion can leave background work, and an exit can leave only
one Ready seat. Quiet-round termination does not bound an all-busy wait because the
minimum-free check stops seat traversal and further round counting.
