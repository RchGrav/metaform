# MoltedFleet: independent pass on GF1-GF12

Code inspected: `source/crates/roundtable/src/jev.rs` (207 lines), `source/crates/roundtable/src/turn.rs` (576 lines), and all files under `source/crates/roundtable/resources/{jev,feedback}`.

Key fact that governs most verdicts: the copied `source` tree is **partial**. It has `jev.rs` and `turn.rs`, but not `rules.rs`, `engine.rs`, `prompts.rs`, or `resources/topic_sameness.md`, all of which `jev.rs`/`turn.rs` `use` or `include_str!`. So a finding whose only support is a line in one of those absent files (notably GF2's `src/turn.rs:225` and GF3's `src/engine.rs:510-513`) cannot be fully verified here. I mark those "right in framing, citation unverified" rather than trusting or dismissing them.

Verdict vocabulary: **Right** (finding is correct; change follows), **Partly** (diagnosis right, prescription needs narrowing), **Wrong** (finding is mistaken), **Right-but-passes-gate** (true statement that does not meet the stated pass condition).

## GF1 (Blocker): "three 70% conditions" / "returns reasons"

**Right.** The two dependency lines (element.md:16, :19) say "three 70% conditions" and "with reasons". Both are stale against the element's own `rules`:
- `jev::GATES` has 3 gates but `contribution_questions()` returns 5 questions (3 `noul` gates + 2 `score` questions; jev.rs:43-59), and `on_judged` filters all five (turn.rs:207-210).
- `Jev::ask` returns `BTreeMap<String, f64>` only (jev.rs:152-175); it returns no prose. The prose the author sees is the owner's fixed per-check feedback files loaded in `prompts::rejected` (feedback/*.md), not something JEV emits.

Why the change matters: the dependency contract is what `code.manager.chat.group` designs against. A caller reading "three 70% conditions" would size the payload and the pass rule wrong.

Change (description only):
- element.md:16 -> "Accepts or vetoes each transmitted contribution against the owner's five checks (three 0.70 gates, two 3.0 scores), with veto reasons."
- element.md:19 -> "...Returns one confidence per check (a 0-1 confidence for each gate, a 0-5 score for each score) in one request through OpenRouter; it returns numbers only, not prose."

## GF2 (Blocker): veto does not show confidence to the author

**Right in framing, citation unverified.** The described behavior in the `decisions/reasons` entry (element.md:94-98: "names each failed condition in plain words **with its confidence**") does not match what the visible code does. `on_judged` builds the author's notice from `prompts::rejected(&failed)` where `failed` carries `(name, value)` (turn.rs:209-216), and publishes the numeric confidences separately on the chair-facing `Contribution.reasons` as `"{name} {value:.2}"` (turn.rs:225). The author-facing strings are the fixed owner feedback files, which are label+prose and carry no number. That part is verifiable from the materials present. The claim that this is specifically `src/prompts.rs:44-54` rests on a file not in `source`, so I do not lean on the line citation; the behavior claim stands on turn.rs:216 and the feedback/ files alone.

Change (description): rewrite element.md:94-98. The delivered notice is the owner's prefix plus, per failed check, the owner's fixed feedback line for that check (and for scores, the band's feedback), with **no confidence shown to the author**. Confidences are visible only on the chair-facing event.

Two notes teammates should weigh before finalizing:
1. This is a genuine spec-vs-code conflict, but it may be a *code* bug rather than a bad description. The owner's stated purpose of the reasons (element.md:97, and the "which condition to address" intent) argues the author benefits from seeing which check and how far it fell. That is a decision for the owner, not the reviewer. The honest resolution is: state what the code does, and flag "show confidence in the author notice" as an open decision.
2. The owner decision at element.md:117 says the gates use the owner's questions *word for word with no field names*; `prompts::rejected` is the fixed feedback, which is consistent with "reasons are fixed prose", further supporting "numbers, not prose, come from JEV".

## GF3 (Blocker): "truncation / short deadline / never waits"

**Partly.** Three sub-claims:
- **No truncation: Right.** `submit` (turn.rs:125-155) never truncates. Over-length replies are *blocked* (`too_long`, turn.rs:129-145); judging-off and no-key paths share the full text (turn.rs:148-154). The word "truncated" in element.md:110 is wrong.
- **No deadline: Right.** `jev.rs:1-3` states "No timer: it gets a reply or an error". There is no deadline in `submit`/`ask`.
- **"The table never waits on JEV": Contradicted by the visible code.** `submit` sets `self.judging_floor = Some(ticket)` for a floor (non-after-work) turn and only clears it in `on_judged` (turn.rs:170-189). `resolve_reply` returns `None` for a floor contribution that went to JEV (turn.rs:112-115), i.e. the floor outcome is withheld until the verdict lands. So the next floor turn does wait for the verdict. The GF3 line citation `src/engine.rs:510-513` is in an absent file, but turn.rs:170-173 is sufficient to establish the wait on its own.

Why it matters: element.md:110 asserts "No blocking retries, and the table never waits on JEV", and RT-G10... (see GF9) says the opposite. That is a direct internal contradiction; the engine spec and this element must agree on one behavior.

Change: split the decision. Either
(a) keep the code's behavior and fix the description: judging, when on with a key, is synchronous for floor turns (the next floor turn waits for the verdict); there is no deadline; failure shares unjudged and notifies; **and delete "truncated to the allowance" everywhere it appears**; or
(b) keep the owner statement's intent ("optional, never halts") and change the code to release the floor after a bound. Because the owner explicitly rejected waiting (element.md:109-111), (b) is the owner-aligned direction, but it is a code change, not a description change, and the reviewers are flagging description drift, so the least-surprising immediate fix is (a) plus an open issue that the code still blocks a floor turn.

## GF4 (Blocker): "objective + current topic's messages + window is a setting"

**Partly — the state content claim is Right; "window is a setting" is Wrong.**
- **No objective: Right.** `contribution_state(topic, log, round, new_message, questions)` (jev.rs:78) builds `{topic, conversation, new_message}` (jev.rs:92). No objective is passed in or included.
- **Last 4 completed rounds + current: Right.** `first = round.saturating_sub(HISTORY_ROUNDS)` with `HISTORY_ROUNDS = 4` (jev.rs:62, :80). The test at jev.rs:189-199 pins rounds `[6,7,8,9,10]` for round 10.
- **Limits are constants, not settings: Right.** `STATE_PLUS_QUESTION_TOKENS = 32_000` and `REQUEST_TOKENS = 64_000` (jev.rs:64-66) are `const`. The decision (element.md:103) says "The window size is a setting"; it is not. What *is* a setting is nothing here; the round count is also a const.

Change (description): element.md:103 must describe the state as topic + last 4 rounds + current round + new_message, no objective, with two **constants** (32k state+longest-question, 64k request). If "setting" was intended as future capability, move it out of `decisions` into `elephant.gaps` or an investigation. Restate the objective omission explicitly, because RT-G17's name ("JEV sees only recent rounds") is fine but the decision's promise of objective is not.

## GF5 (Major): unstated behaviors in rules[4]

**Right on all five sub-points, and each is verifiable in the visible code:**
1. **Chair guidance in conversation: Right.** `Entry::Chair` is included with `{"name":"Chair","text":...}` (jev.rs:85). The rules say "accepted messages"; chair text is not a message.
2. **Cannot-fit shared unjudged + loud notice: Right.** `contribution_state` returns `Err` when even empty state overflows (jev.rs:97-98); `submit` turns that into `notice("error", ... "shared unjudged")` and accepts (turn.rs:163-167). The rules only say "shared unjudged and the error is shown" (element.md:48), which is close but lacks the "does not fit" trigger and the "loudly" chair notice.
3. **Topic is the one at turn start: Right.** `submit` uses `topic: self.seats[i].prompt_topic` (turn.rs:147) and indexes `self.topics[(judgement.topic-1)]` (turn.rs:160). So a topic change mid-turn does not affect the pending judgement.
4. **Missing/out-of-range answers are errors: Right.** `ask` errors on missing answer, non-numeric, or out of `0..top` (jev.rs:168-171). This is the mechanism behind "fails" in rules[5].
5. **After-work replies do not block turns: Right.** `judging_floor` is set only `if !judgement.after_work` (turn.rs:170). So after-work replies are judged asynchronously and never gate the floor.

Change (description): expand rules[4] (element.md:47) to state: conversation = accepted messages **plus chair guidance** of last 4 rounds + current; a candidate too large to fit is shared unjudged with a chair error notice (not a rejection); topic is fixed at turn start; any missing/out-of-range/malformed answer is an operational failure (shared unjudged); after-work replies are judged in background and never hold the floor.

## GF6 (Nit): superseded "evaluation happens once, before distribution"

**Right-but-passes-gate / Partly.**
- "Evaluation happens once, before distribution is marked superseded but is still current": **Right in the listing sense.** It is in `superseded` (element.md:152-155) yet the code still evaluates once per message before it is logged/shared via `accept` (turn.rs:125-182); nothing replaced it. A reader of `superseded` would infer the rule changed; it did not. That is a documentation defect worth fixing (move it back to `rules`, or say what replaced it).
- "With judging off or no key, no error is shown, only an event note": **Partly/Right.** `submit` uses `accept(..., Some("unjudged: judging is off"))` / `"no OpenRouter key"` (turn.rs:148-155), which *publishes* a `Contribution` with `note`, i.e. a chair-facing bus event, and no `notice("error", ...)`. The rules[5] phrase "the error is shown" (element.md:48) is vague about where; this finding correctly identifies that for off/no-key it is a note on the event, not a displayed error. (For the JEV-failure path, `on_judged` does call `notice("error", ...)` — turn.rs:200 — so "error is shown" holds there.)

Change (description): move "Evaluation happens once, before distribution" out of `superseded` (it is current). Clarify rules[5]: "shown" means a chair notice event; for off/no-key it is an informational note on the accepted contribution, for a JEV/transport failure it is an error notice and the contribution is accepted unjudged.

## GF7 (Major): dependency lines vs rules vs reasons decision

**Right, and it is the same root cause as GF1 — do not resolve it twice in inconsistent words.**
- Dependency lines say "three 70% conditions" (element.md:16) and "three conditions with reasons" (element.md:19) while rules say five checks incl. two 0-5 scores (element.md:43-46). This is a straight contradiction, already covered by GF1's fix.
- The "reasons" decision says JEV returns probabilities, not prose (element.md:95), but both dependencies say "with reasons"/"with reasons for any that fall short". If "reasons" in the dependency means JEV proffers prose, that is false (ask returns f64s only); if it means the code synthesizes reasons from owner feedback, say so. **This is a wording defect in the dependency lines, not in the decision**: the decision is correct and the dependency text is sloppy.

Change: in element.md:16 and :19 use "with per-check numbers" and reserve "reasons" for the owner-feedback lines the manager emits. State once, in the decision, that *reasons = fixed owner feedback keyed by failed check*.

## GF8 (Major): judging-context decision vs JEV's state rule

**Right.** element.md:103 (decision) describes objective + current topic's messages under "64K"; rules[4] (element.md:47) describes topic + last four rounds + current round within 32,000 and 64,000. The discrepancies:
- objective present in decision, absent in rule and in code (jev.rs never receives it) — see GF4.
- "64K" single limit in decision vs two limits in rule and code (`STATE_PLUS_QUESTION_TOKENS`, `REQUEST_TOKENS`, jev.rs:64-66). The two limits are **unexplained** in the rules. Code intent (comments jev.rs:63-66): 32k bounds state + the longest single question so one gate question plus state fits; 64k bounds the whole multi-question request. The description should state that, because a reader cannot tell why 32k and 64k coexist.
- "what topic holds when topics are off is unstated": **Right** in the description; in code the caller always indexes `self.topics[(topic-1)]` (turn.rs:160), so a topic string always exists; but topics-off behavior is not in this element's text. Mark as description gap to reconcile with the topic part.

Change: collapse decision and rule to one description: state = topic string + last 4 completed rounds + current round + new_message; no objective; limits 32k (state+longest question) and 64k (full request) are constants with the reason for each; note how the topic string is supplied when topics are off (defer the exact semantics to the topics element but say "the active topic string, which is always present").

## GF9 (Major): owner "JEV is optional" vs rules vs engine gate RT-G10

**Right.** element.md:110 (owner decision) says: truncated to the allowance, failure/no-answer within a short deadline is shared unjudged, chair notified, no blocking retries, table never waits. Reality in visible code: no truncation (GF3), no deadline (GF3), floor turn *does* wait (turn.rs:170-173) — and element.md:206 itself cites RT-G10 "next turn waits for JEV's verdict", which is the exact opposite of "never waits". The failure marking is `unjudged: JEV unavailable (...)` on the contribution note (turn.rs:200-201) and an error notice; element.md:48 says "the error is shown" without saying where. Reconciliation: all three texts must say the same thing.

Change:
- Delete "truncated to the allowance" from element.md:110.
- Delete or define "short deadline": there is no timer (jev.rs:1-3); either remove the phrase or add a timer to code (a behavior change, needs owner).
- Resolve "never waits" vs RT-G10 in one direction. Given owner's explicit "Halting can prove more expensive", the intended design is *non-blocking*; the code's `judging_floor` is therefore a code defect against the owner, not a description defect. But the reviewers are scoping the description. Recommended: description records current behavior truthfully ("a floor turn waits for the verdict; after-work turns do not"), and a separate open issue says the owner wants the floor not to block, so the floor-wait must be removed.
- Say where the error is shown: chair event notice; contribution carries `unjudged: ...` note. Do not say "the error is shown" bare.

## GF10 (Major): terminology

**Partly — most points Right, one is unfair.**
Right: "JEV", "owner's prefix", "score band", "moderator", "true-means-pass statement", "Python's chassis", "no TRUE/FALSE criteria and no field names" are undefined. "owner's prefix" is `feedback/prefix.md` (verifiable). "score band" is the 0-2 banded feedback `value-{0,1,2}.md` / `auditability-{0,1,2}.md` (verifiable by the filenames). "moderator" is in `resources/jev/auditability.md` and is not expanded. "true-means-pass statement" is decision language at element.md:91 with no definition. "Python's chassis" refers to a prior Python implementation not linked here. "no TRUE/FALSE criteria and no field names" refers to the archaeology TRUE/FALSE prompts; undefined in-context.
Wrong-ish: "JEV is never expanded" is true but low-value; JEV is the element's subject and the references point to `crates/roundtable/resources/jev/`. "value/auditability rubrics pointed to only by a directory": the files are named `value.md`/`auditability.md` under that dir, so the pointer is adequate to *find* them but not to read their scales; a one-line summary of each rubric's 0-5 levels would fix it. "Jev's documentation" is undefined — Right, and it matters because it is the basis for "accuracy falls as irrelevant state grows" (element.md:103); that is an unsupported claim with no link.

Change: add a short glossary to the element (JEV = the OpenRouter decisions endpoint at `DECISIONS_URL`, model `~typesafe/jev-latest`; owner's prefix = `feedback/prefix.md`; score band = the 0/1/2 feedback file matching the failing score's value; moderator = whoever reads the table record). Replace "Jev's documentation says ..." with the claim's source or drop it. Summarize the two rubrics in one line each.

## GF11 (Nit): superseded one-inference / once-before-distribution

**Right, same defect as GF6 for the once-before-distribution entry; the one-inference entry is lightly different.**
- "may be requested in one inference" is marked superseded (element.md:148-151) but rules[0] still says "One JEV request per message holds five checks" (element.md:43) and code does `ask` once (turn.rs:177-180). So the superseded list is misleading: the one-inference property is *still live*. Right.
- The description never says what replaced the superseded entries. Right: that is the actual defect (a `superseded` layer should name the successor).

Change: either remove these two entries from `superseded` (they are current) or edit each to say what it was replaced by. Best: keep them out of `superseded`; once-before-distribution and one-inference are current rules and belong in `rules`. If they were momentarily changed during the 2026-11-07 churn and reverted, record that in `investigations`, not `superseded`.

## GF12 (Nit): elephant gap wording

**Right-but-passes-gate.** "JEV requests are not saved in the table record, so a decision can only be rebuilt afterwards" is confusing and, as written, slightly false: the decision *can* be rebuilt only by re-running JEV (not by inspecting a stored request/answer). That is exactly a tension with the auditability score: auditability is judged on the *author's* message content, not on JEV's own request record, so the two are separable — but the gap should say so. In the code, `on_judged` drops `judgements` after use (turn.rs:185) and only the numeric `scores` and `reasons` survive on the published `Contribution`; the `state` sent to JEV is not persisted. So an auditor sees outcomes but not inputs.

Change: reword the gap to: "JEV's request state is not persisted in the table record; only the returned numbers and the failed-check lines survive on the contribution event. A decision can be checked for its recorded outcome but not re-derived from stored inputs." Optional: mention that this does not affect the auditability *score*, which rates the author's message, and that persisting the state is a candidate fix.

## Cross-cutting: which of these are description bugs vs code bugs

Worth stating once so the group fixes the right artifact:
- **Description bugs (fix element.md):** GF1, GF4 (setting), GF7 (wording), GF8, GF10, GF11, GF12, the "truncated" and "short deadline" and "never waits" phrases in GF3/GF9.
- **Code bugs against the owner (fix code, then describe):** GF2 (author not shown confidence — owner's purpose suggests showing it), GF3/GF9 (floor turn blocks, owner said never block). These two are the ones where "make the description match the code" would entrench the wrong behavior.

That distinction should lead `resolution.md`: each finding right/not-right, and for the right ones whether the fix is text-only or a code change.