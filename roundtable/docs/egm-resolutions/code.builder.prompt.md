# Participant turn prompt — review resolutions

Decisions by SmoothShift, 2026-11-07. This resolves the findings; it does not implement the proposed source or description edits.

## Evidence and precedence

The supplied snapshot contains only `source/crates/roundtable/src/turn.rs` and `prompts.rs`. Resource templates, `engine.rs`, `rules.rs`, and the referenced engine document are absent. References below use paths relative to `source/crates/roundtable/`. Assertions about absent files are identified rather than presented as independently verified.

The owner's explicit no-characters-line decision and the active rule against a generic reply instruction take precedence over older conflicting decisions. Preserve the owner-authored templates. A historical decision must be marked superseded or unimplemented when it does not describe current behavior; merely leaving it in the decisions list perpetuates the contradiction.

## Individual findings

### GF1 — Accept the contradiction; change the description

`turn_prompt` adds no PASS/WORK instruction (`src/turn.rs:31–83`). The stronger claim about all resource text cannot be checked from this snapshot. Nevertheless, the reply-convention decision directly conflicts with the active “no instruction to reply” rule.

Mark the November 5 reply-convention decision superseded by that rule. State that the builder emits no generic contribution/PASS/WORK instruction. Do not restore one to satisfy a stale decision. Parser behavior belongs in the reply-handling description and must be verified separately; recognizing a control value does not establish that this builder must advertise it.

### GF2 — Accept the implementation gap, with a resource-evidence limit

Neither source file constructs kickoff strategy guidance or explains `advance` and `feedback`. Electing a head, as quoted by the reviewer, does not ask participants to agree how to coordinate. The absent templates prevent independently confirming the categorical claim that no prompt contains this material.

Retain the explicit kickoff and tools decisions as intended requirements, but label them unimplemented in the supplied builder. Unlike the allowance and reply-convention decisions, there is no explicit later owner prohibition of strategy or tool guidance. Close the gap by adding concise first-turn guidance in the builder's delivery, outside the verbatim owner templates: agree how to coordinate and whether to divide work or work independently; consider electing a head; explain that `advance` ends the topic and can name the next, and `feedback` rates another participant's behavior for identity/accolades. Describe the head as the normal user of `advance`, not an enforced permission boundary. Verify the actual tool interface before choosing final wording.

Add these requirements and their location to the rules. Keep strategy contributions in the normal discussion loop, with no separate phase. This is proposed implementation work, not a claim that it already happens.

### GF3 — Accept; remove the stale prompt dependency

The builder does not read `seat.limit` while assembling prompts. It reads the limit when submitting a contribution (`src/turn.rs:125–145`). Remove or retire `code.quota.character` as a dependency whose purpose is to tell the participant its current allowance. If the functional map also covers reply resolution, record the enforcement dependency there instead.

The no-characters-line rule concerns the routine discussion allowance banner. It does not prohibit a special topic-proposal request stating its own limit (`src/prompts.rs:85–86`) or a block notice explaining an overlong contribution. Preserve those distinctions.

### GF4 — Partly accept; correct the reviewer's overstatement

The allowance and characters-removed promises are stale: discussion contributions exceeding their limit are blocked before evaluation, not shortened (`src/turn.rs:128–145`). Update the delta-delivery decision and log dependency to say “pending participant notices, including evaluation rejection and overlength blocking,” without promising an allowance or removed-character count.

The description does **not** explicitly promise the objective every turn. The log dependency names topic and objective as available context; the delta-delivery decision names only a changed topic. Reject that portion of the finding as phrased. Still clarify that the configured objective is inserted into the participant template on the first turn (`src/turn.rs:69–78`), while subsequent prompts rely on session continuity. Do not add repeated objective text.

Also avoid the unqualified claim that “truncation no longer exists”: topic proposals are still truncated to `PROPOSAL_LIMIT` in `on_proposal`. The correction applies to discussion contributions.

### GF5 — Accept; document the complete delivery order

Replace the abbreviated ordering rule with the actual assembly sequence (`src/turn.rs:34–68`):

1. Round label, only for a discussion request.
2. First-turn identity profile, only if an identity store and name exist and the stored profile has prior ratings.
3. Pending participant notices, only for a discussion request, in their stored order.
4. Changed-topic line, when topics are enabled, this is not the first prompt, and the participant has not seen the current topic index.
5. Unseen log entries in log order: other participants' accepted messages and chair entries interleaved. Own accepted messages are omitted.
6. Any request-specific `ask`, last.

Parts are separated by blank lines. Notices include overlength blocking and evaluation rejection; include feedback-recording failures in the notice contract as reported by the reviewer, while noting that their `engine.rs:892` producer is outside this snapshot. Do not promise a separate rejection-first sort within the notices: the builder simply extends the stored list. The optional identity profile precedes notices, but the participant's notices still precede other participants' contributions.

### GF6 — Accept; qualify the scope of the rules

The round line and notice consumption are controlled by `discussion`; `ask` is appended independently (`src/turn.rs:34–35,52–54,67,82–92`). Specify that floor turns and workspace-review turns are discussion requests. A review request therefore receives the round line and notices **and** has its review ask last. A topic-proposal, rating, receipt, or results request is a different kind of request and should not be described as receiving discussion notices.

The supplied function establishes the conditional behavior; full verification of how each activity passes `discussion` requires the absent caller. No runtime change is justified by this finding.

### GF7 — Accept; same correction as GF3/GF4

Retire the allowance-reporting dependency and supersede the allowance/removed-characters portions of the delta-delivery decision. Preserve reply-limit enforcement and its explanatory blocking notice. This is the same underlying defect as GF3/GF4, not an additional reason to restore an allowance banner.

Correct stale source documentation too: the `turn_prompt` comment (`src/turn.rs:22–25`), `submit` comment (`src/turn.rs:124`), and module comment (`src/prompts.rs:1–4`) still describe truncation or a characters line. Replace those comments with the actual ordering and block-before-evaluation behavior. Runtime code need not change for this correction.

### GF8 — Accept the ambiguity; do not assume a WORK dependency

Resolve the description conflict as in GF1. `resolve_reply` handles `Reply::Pass`, `Reply::Empty`, and `Reply::Contribution`; it contains no `Reply::Work` branch (`src/turn.rs:97–110`). Work-related state and `after_work` do not prove that the literal text WORK is a required protocol command.

Consequently, the assertion that the engine depends on both literal commands is not established by the supplied code. Document exact recognized syntax and any working-state mechanism in the engine/reply-classification element after inspecting those implementations. Do not introduce a WORK instruction on the strength of this finding.

### GF9 — Accept the documentation gap; distinguish implemented from planned

Put the first-turn kickoff/tool requirements from GF2 in the rules and explicitly label their current implementation status. Do not say that the owner templates already contain them without checking those files.

Chair delivery is implemented: `Entry::Chair` becomes `Chair: text`, interleaved with accepted messages in unseen-log order (`src/turn.rs:60–64`). Document that location. This means the next successfully delivered prompt, potentially a special request, rather than necessarily the next floor turn. The statement that chair guidance bypasses evaluation concerns log admission elsewhere; this builder demonstrates delivery, not that bypass. Preserve it as an upstream contract and verify it at the producer.

### GF10 — Accept; clarify sources and necessary terms

Describe two distinct owner-authored resource inputs, both loaded by `prompts.rs`: `resources/roundtable_prompt.md` is the outer first-turn template; `resources/participant_prompt.md` is the nested participant template, filled with `cfg.objective`. Split the existing system-prompt dependency or enumerate both resources within it; do not invent an unknown functional-map identifier. The current topic comes from `self.topic()`, not from the log traversal. The configured objective also does not come from that traversal.

Define the terms used by this element:

- `R<t>-<m>`: topic index and one-based accepted-message sequence within that topic, **not** discussion round. `accept` constructs it from `j.topic` and accepted log entries (`src/turn.rs`, `accept`).
- `Current delivery:`: the outer template's reported boundary before the rendered delivery. The builder supplies this via `{{delivery_json}}`; despite the placeholder name, its value is plain text joined with blank lines. Confirm the literal marker in the resource.
- Disposition: the participant-facing outcome notice, such as evaluation rejection or overlength blocking.
- JEV: the contribution evaluator; ACP: the participant session protocol whose ongoing conversation supplies continuity.
- Chair: the human/operator supplying guidance; distinct from an elected participant head.
- Accolades: ratings-derived standing associated with a persistent participant identity.
- Work notes: incidental working commentary included in returned participant text. The builder forwards accepted message text as stored; it does not isolate notes from contributions.

These are description improvements. No need to remove the identity profile or rewrite the owner's prompts.

### GF11 — Accept; make topic delivery explicit

Add the exact condition from `src/turn.rs:57–59`: after the first prompt, topics enabled plus an unseen topic index produces `Current topic: …` before log entries. The first-turn wrapper receives the current topic instead. Only the current topic is sent; multiple intervening changes are not replayed as topic history.

Document that committing any delivered prompt updates `seen_topic` and `seen_log`, while only a discussion prompt clears notices (`src/turn.rs:85–92`). A special request can therefore deliver and acknowledge the changed topic before the next floor turn. Preserve this behavior and the first-turn objective/session distinction from GF4.

### GF12 — Accept the wording ambiguity; qualify external claims

Rewrite the round-label rule to state that it chooses **one** label: normally `Round N of T`, replaced near the end by the applicable `3 Rounds Remain`, `2 Rounds Remain`, `1 Round Remains`, or `Final Round`; an unlimited discussion uses `Round N`. They are alternatives, not accumulated suffixes. This records the intended meaning; checking exact boundaries, including short discussions, requires `rules::round_label`, which is absent. The builder only pushes its returned label once (`src/turn.rs:34–35`).

Use the exact topic name `kickoff strategy` for the reported engine-document cross-reference. Correct the referring document if the reported `kickoff` reference exists; that document was not supplied. Neither issue warrants changing prompt assembly.

## Addendum — dissenting/correcting notes (SecureTarget)

Two points where a separate review of the same two files reached a different or sharper
conclusion, recorded so the group can weigh them rather than lose them:

- **GF2 / GF9 (contest the proposed behavioral change).** This resolution proposes adding
  first-turn strategy/tool guidance to the builder's delivery. A separate reading argues against
  implementing it in `turn.rs`: `rules[3]`, the `elephant` "built" line, and the `turn_prompt` doc
  (src/turn.rs:28-30) all state the first turn is *exactly* the owner's roundtable prompt with the
  owner's participant prompt nested inside it, and the `kickoff strategy` decision is explicitly
  tagged `"status": "per owner statements; wording open for owner"` — a proposal, not shipped
  behavior. Adding prose to `turn_prompt` would change the delivered first-turn prompt and
  contradict `rules[3]`. The safer resolution is to mark those `decisions` entries
  unimplemented/superseded and raise "where should this text live" to the owner, as the existing
  `investigations: spec section 11 vs prompt` note already does for owner-authored prompt text.
  It is correct that there is no explicit owner *prohibition* of the text; the objection is to
  changing code on the strength of a stale proposal, not to the text's desirability.

- **GF8 (accept the sharper correction).** The claim that the engine depends on a literal
  first-line **WORK** command is an overstatement. `resolve_reply` (src/turn.rs:97-110) branches on
  `Reply::Pass`, `Reply::Empty`, `Reply::Contribution` only; there is no `Reply::Work` branch, and
  `after_work` is state passed to `submit`, not a parsed control value. The resolution's "do not
  assume a WORK dependency" is the more audit-safe reading and should stand. PASS is genuinely
  parsed (src/turn.rs:99-101, 320-333), so the open question is specifically where *PASS* and the
  working-state mechanism are communicated, not where PASS/WORK are advertised as a pair.

## Resulting scope

Most corrections belong in the description and stale source comments. The proposed behavioral addition is the still-unimplemented first-turn strategy/tool guidance in GF2/GF9, subject to checking the complete templates and tool interface to avoid duplication or inaccurate instructions. Keep the owner templates verbatim, omit routine allowance banners and generic reply directives, and preserve blocking, delta delivery, profile text, and chair/message ordering. Full rendered-prompt storage is another upstream claim: these two files do not establish persistence, so its verification belongs to the discussion-record element.

## QuickCoyote addendum — corrections and the one finding both resolutions get partly wrong

I re-read both source files (`turn.rs`, `prompts.rs`) and the `element.md` text. I agree with the substance of the existing resolutions on GF3, GF5, GF6, GF7, GF10, GF11; I record only where I differ, plus line evidence the earlier passes left implicit.

### GF4 — reject the "objective every turn" half and the "objective appears twice" gap
The reviewers say the description claims the objective "every turn". The description does not: the `wants` entry for `data.log.discussion` says the log *provides* "the current topic and objective" as available context; `turn_prompt` never reads `cfg.objective` except on the first turn (`src/turn.rs:70`, `prompts.rs:12-14`). The delta-delivery decision names only "the topic when it changed". So the Major's first and third clauses are wrong as phrased; only the allowance/"characters removed" clause survives. Note also that the `elephant.gaps` line "objective appears twice on the first turn" is a *known, accepted* duplication — the objective is filled into `{{roundtable_prompt}}` and again into `{{custom_roundtable_prompt}}` via `participant_prompt` (`prompts.rs:70,78`). It is not a finding about delta delivery and should not be "fixed" by deleting either substitution; the owner's template owns that.

### GF8 — "engine depends on PASS/WORK" is not supported; only PASS is parsed
`rules::classify` branches are exercised at `turn.rs:99` (floor) and `turn.rs:320` (proposals), and `resolve_reply` matches `Reply::Pass | Reply::Empty | Reply::Contribution` only (`turn.rs:99-110`); there is no WORK branch in this snapshot. `after_work` is a boolean the caller threads into `submit`, not a parsed verb (`turn.rs:97,147`). So the ambiguity GF8 raises is real (description contradicts rules) but the *premise* ("which the engine depends on") should be narrowed to PASS. Resolution: fix the description conflict (mark the reply-convention decision superseded by the "no instruction to reply" rule); do **not** add a PASS instruction to the prompt without an owner decision, and do not add WORK at all.

### GF2 / GF9 — agree with SecureTarget's dissent, sharpen the reason
Adding kickoff/tool prose inside `turn_prompt` would break three independent statements of invariant: `rules[3]` ("The first turn is the owner's roundtable prompt with the owner's participant prompt inside it and the first turn after 'Current delivery:'"), the `elephant.built` line (`built`), and the doc comment at `src/turn.rs:28-30`. The only place builder text can legally go without touching that invariant is the `delivery` slot (the part after `Current delivery:`), which `roundtable_prompt` fills last (`prompts.rs:79-82`). If the owner wants the kickoff ask, that is the insertion point — and it must be raised to the owner because the kickoff decision is tagged `"wording open for owner"`. My verdict: mark GF2's implementation as *unresolved pending owner wording*, not "add to delivery now". The decision is right that the capability is missing; the code change is premature.

### GF3 — the dependency is real but belongs to reply resolution, not this element
`seat.limit` is read at `turn.rs:126` and enforced at `turn.rs:130`. The `code.quota.character` want in *this* element is wrong because `turn_prompt` never reads it. The clean fix is to move the dependency to the element that owns `submit`, or to rename it "reply length limit (enforced on submit)" and drop "reports the allowance". Do not delete the limitation from the map: the block notice (`prompts::too_long`, `turn.rs:131`) is a participant-facing disposition that this element *delivers* but does not *produce* — which is exactly why the notice contract needs a producer reference.

### GF5 note on ordering within notices
The rules abbreviated order is incomplete, correct. But note the finer point: notices are appended in *arrival* order (`seat.notices.push` at `turn.rs:131`, `216`; cleared only on commit at `turn.rs:89`), so a rejection from a past round can follow a too-long notice from a later one. The rule should say "in the order they arose", not "rejection reasons, then …", or a reader will expect rejection-first sorting that the code does not perform. This is a documentation fix only.

### GF12 — one correction the earlier passes did not make explicit
`round_label` is called once and pushed once (`turn.rs:34-35`); `self.rounds`/`round_no` are supplied by `rules`. The description's phrase "Round N of T, then '3 Rounds Remain'" reads as concatenation because of the word "then"; the rule should state that exactly one label is produced. This is a description fix, no code change; the boundary table (when T=3,4) lives in `rules::round_label` and is out of scope here.

### Scope verdict
Of the twelve findings: GF1, GF5, GF6, GF9, GF10, GF11, GF12 are right and are description fixes. GF3 is right about this element but the fix is to relocate the dependency, not delete enforcement. GF4 is half-right (allowance clause only) and misphrases the objective clause. GF7 is right as a staleness consequence of GF3/GF4 and needs no separate change beyond those. GF2 is right that the capability is missing but wrong to imply a code fix is ready. GF8 is right about the contradiction but overstates the WORK dependency. No finding justifies new prompt code without an owner decision, except the already-open "where does kickoff text live" question.
