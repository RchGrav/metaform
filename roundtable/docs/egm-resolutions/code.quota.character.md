# Reply limit: resolution of GF1–GF12

Reconciled by SpinyShark against the supplied source. These are decisions about changes to make, not claims that implementation changes have been applied. Source citations below are relative to `source/crates/roundtable/src/`. Only four Rust files are supplied: README, prompt templates, gate registry, and the reviewer's tests are unavailable for independent verification.

## Common policy decision

Prefer the current specific rule, “the recovery limit (1,024) once”, over the comparative phrase “one larger reply”. Recommended resolution: an ordinary discussion prompt uses `base_allowance` (default `None`, unlimited); the next successfully dispatched discussion prompt after a busy skip uses exactly `Some(recovery_allowance)` (default 1,024), independently of the base. This can restrict an otherwise unlimited reply or replace a base above 1,024 with 1,024. Replace “larger” with “one reply with the recovery limit”. This is a resolution recommendation from the supplied description, not an additional owner quotation.

Do not silently introduce `max(base, recovery)`: that would implement a different rule for bases above 1,024. Recovery is one pending flag, not accumulated credits. Repeated skips coalesce. Assignment and consumption occur on successful dispatch of the next discussion prompt, including a review whose reply is a contribution. A pass, veto, length block, or later prompt failure does not restore it; failure to dispatch leaves it pending. A reply already in progress keeps the limit assigned to its original prompt.

Define “busy skip” as `give_floor` encountering a Ready seat that is not free to speak and skipping its scheduled opportunity (`engine.rs:531–575`). Starting tool work in an already issued prompt is a distinct transition; it does not itself grant recovery. Proposal and rating prompts do not consume recovery. These explicit boundaries resolve the ambiguous parts of GF5 and GF7.

## GF1 — Right: code contradicts the unconditional recovery rule

`limit_for` exits through `base_allowance?` before checking recovery (`engine.rs:396–399`). The base defaults to `None` (`config.rs:157–158`). Recovery therefore never operates in the default configuration, contrary to rules[2], the manager want, and the built claim.

**Change code:** check `recovery_due` first, returning `Some(recovery_allowance)` when true and `base_allowance` otherwise. **Change description:** state explicitly that recovery applies with no base and replaces any configured base. The reviewer's test-coverage assertion cannot be verified here; include the unset-base case when implementing the fix.

## GF2 — Right: the participant is not told its effective allowance

`turn_prompt` never renders the effective limit (`turn.rs:31–83`). `FloorGiven` publishes it on the bus (`engine.rs:611`); the supplied code does not deliver that event as participant prompt text. A static template cannot reliably convey a changing per-seat allowance.

**Change code:** tell the participant the effective limit in every Floor and Reviewing prompt, including the counting unit and the consequence of exceeding it. Communicate a return to unlimited when applicable. Keep the participant-facing want rather than weakening it to chair telemetry.

Compute the limit once in `offer` and pass it into the builder. Do not read the old `seat.limit` inside the builder: `offer` computes the new value at line 596, builds the prompt at 597, and only stores the field at 604. Use the same computed value for prompt wording, stored enforcement limit, and the floor event. Update the stale prompt-format comments.

## GF3 — Right: bank-era decisions appear active

The four 2026-11-05 decisions about vetoes, accepted contributions, topics, and characters retain bank/reset/truncation behavior that the current code lacks. `Seat` holds a limit and a pending-recovery flag (`engine.rs:83–86`); `submit` blocks excess length (`turn.rs:125–146`).

**Change description:** mark these decisions superseded by the 2026-11-07 credit-removal and blocking decisions, preserving historical text and dates. Replace their active meaning with the assignment/consumption policy above. Retain the still-valid Unicode scalar counting unit in a new active statement. Do not reintroduce a bank or a reset to 512.

## GF4 — Right about scope and missing consequences

Discussion contributions are never length-truncated in `submit`. Topic proposals follow a separate path: `on_proposal` calls `truncate_to` with `PROPOSAL_LIMIT = 512` (`turn.rs:321–325`; `rules.rs:19–38`, RT-G13). An unqualified claim about all messages is too broad.

**Change description:** scope this element's no-cutting guarantee to discussion contributions, including reviews and work completions. Explicitly cross-reference the separate proposal rule: proposals are bounded to 512 Unicode scalar values at a grapheme boundary. Keep that separate behavior and helper in this resolution; discussion blocking does not remove proposal truncation. Narrow the elephant's broad wording too.

Record that length blocking precedes JEV and returns `Outcome::Failed`. For an ordinary Floor reply it counts a failed opportunity. Work/review completions do not consume another opportunity; see GF10. Update `submit`'s obsolete “Truncate, then judge” comment and `truncate_to`'s obsolete general claim that length never rejects contributions.

## GF5 — Partly right: observations verified, but three automatic fixes are not justified

**Replacement can reduce the allowance: true.** A base above 1,024 is replaced by recovery (`engine.rs:398`). Resolve the conflict by adopting the explicit fixed-recovery policy above and removing “larger”. Using `max` changes the specific numeric rule; it is not required to implement it.

**Floor-to-work does not set recovery: true, but not established as a defect.** `on_tool` turns Floor into Working and counts the opportunity as `SkippedWorking` without setting the flag (`engine.rs:670–675`). That prompt still produces a reply (`703–704`); the seat has not necessarily missed a later scheduled turn. Keep this behavior and define the recovery trigger precisely. If a later scheduled opportunity is skipped while it remains busy, `give_floor` grants recovery normally. Distinguish round accounting from the recovery trigger in the description.

**Reviews consume pending recovery: true, and consistent with “next discussion reply”.** `offer` includes Floor and Reviewing in discussion (`engine.rs:595–605`); both replies are submitted as contributions. A skipped seat can complete work, become Idle, and then receive a review while other seats remain busy (`engine.rs:537–550, 689`). The path is reachable. Keep consumption on successful discussion-prompt dispatch and document it. Reserving recovery exclusively for Floor would change the stated contract. Merely leaving the flag set while giving a review the recovery limit risks granting recovery twice.

## GF6 — Right, with a verification limit

`DEFAULT_BASE = 512` is labeled the default (`rules.rs:7–8`) but is unused in the supplied source, while `base_allowance` actually defaults to `None`. Validation rejects `Some(0)` and zero recovery (`config.rs:113–115`), even when the base is unset.

**Change code/comments:** remove the obsolete constant after checking the full repository for consumers; if a real consumer requires it, rename/document its actual purpose. Keep the unlimited default. **Change description:** each configured numeric limit must be at least one; `None`, not zero, means unlimited. Recovery is configurable and must also be positive.

## GF7 — Right about ambiguity; resolved consistently with GF1/GF5

“One larger reply” conflicts with an unlimited base and with a base above recovery. It cannot universally describe a fixed cap.

**Change description:** recovery is exactly the configured recovery limit once, including with no base and with a larger base; afterward the base applies again. State this as an explicit resolution decision, not a discovered owner clarification. GF1 supplies the unset-base code fix; replacement of a larger base already behaves this way. Do not leave incompatible alternatives or introduce an undocumented maximum operation.

## GF8 — Right about stale decisions; the alleged unit inconsistency is not a defect

Supersede the old decisions as in GF3. Counting Unicode scalar values and choosing a grapheme boundary for a cut are compatible operations, not inconsistent length units: `truncate_to` deliberately does both (`rules.rs:23–37`).

**Change description:** discussion length is `text.chars().count()` after outer whitespace is trimmed by `classify` (`rules.rs:50–58`; `turn.rs:129`). Exactly the limit is allowed; greater counts are blocked. Combining marks and multi-scalar emoji can count as multiple characters. Discussion contributions undergo no grapheme-based shortening. Keep the boundary behavior solely in the separate proposal rule. Do not change enforcement to bytes or grapheme counts.

## GF9 — Right; duplicates the missing feature in GF2

The assembled delivery has no dynamic allowance line. A deferred too-long notice reports a past block, not the limit before the participant composes its reply.

**Change code/description:** implement the GF2 announcement for both Floor and Reviewing using the limit for that prompt. Preserve advance information and communicate a return to unlimited. Do not substitute a description saying that the participant must discover a limit by being blocked. GF2 and GF9 need one implementation change.

## GF10 — Right: specify outcome, ordering, visibility, and notification

**Change description to record existing behavior** (`turn.rs:94–146, 52–55, 85–92`; `engine.rs:696–705`):

- Classification trims outer whitespace; pass and empty responses have separate handling. Contribution length is checked before judging or any unjudged acceptance fallback, so the limit also applies with judging off or JEV unavailable.
- An oversized contribution returns `Outcome::Failed`, not a JEV veto. It never reaches JEV or the accepted message log. A rejected `Contribution` event is still published with `accepted=false`, `judged=false`, no accepted ID, and the length reason. “Not shared” means not delivered as an accepted peer contribution, not absent from chair telemetry.
- A normal Floor completion counts the failed opportunity. Working/Reviewing completions use `after_work=true` and do not count another failed opportunity. Work's opportunity was counted when work began; a review is not an extra scheduled opportunity.
- The author gets a queued too-long notice in the next successfully dispatched discussion prompt, including a review. Proposal/rating prompts neither deliver nor clear it. Failed dispatch preserves it. Delivery is conditional on another discussion prompt occurring before the table ends.
- A block or veto does not restore recovery: assignment was consumed when the discussion prompt was sent.

Exact notice wording remains the owner-text gap already identified by the elephant; its template is not supplied here.

## GF11 — Right: identify the authority and timing

**Change description:** the host/chair supplies `TableConfig.base_allowance` and `TableConfig.recovery_allowance` when creating the table. Defaults are unlimited ordinary replies and 1,024 recovery; agents do not control those fields. The supplied command handler exposes no runtime limit setter (`engine.rs:850–910`), so do not claim an existing live chair control changes them. Replace “the owner's length experiment” with concrete behavior; keep provenance separately. No new runtime configuration API is needed to resolve the finding.

## GF12 — Right about stale prose and undefined terms; README content unverified

**Change description:** date the run-1 observation and rewrite “the current spec truncates instead” as a historical comparison with the then-current truncation policy, followed by today's blocking rule. Preserve chronology rather than silently rewriting historical conclusions. Define “busy skip” precisely as above; mark bank/session-mode discussion as archaeology. A bank was accumulated speaking allowance; session mode concerned its historical lifetime across topics.

The referenced README sections are absent from the copy. Audit them in the full repository, point active references to current blocking/recovery guidance, and label obsolete sections historical. The reviewers' suspicion is reasonable, but unseen README content is not established evidence.

## Checks for the implementation follow-up

Verify limits with base unset, below recovery, equal to recovery, and above recovery. Expected post-skip sequences include unlimited → 1,024 → unlimited and 2,000 → 1,024 → 2,000. Repeated skips yield one assignment. Verify review consumption, preservation on failed dispatch, and that starting tool work alone does not grant recovery.

Verify advertised/enforced limits agree on the first recovery prompt and the following normal prompt; exactly-at-limit and over-limit scalar counts; deferred notices; JEV bypass for oversized contributions; and no extra opportunity count for work/review completions. Preserve separate proposal behavior. These are proposed checks, not executed tests: this snapshot contains no Cargo manifest or test suite.
