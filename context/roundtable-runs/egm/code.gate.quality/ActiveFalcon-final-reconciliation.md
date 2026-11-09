# ActiveFalcon: final-round reconciliation

I accept the correction on GF3/GF9: documenting the current floor wait cannot discharge the owner requirement. The main resolution now preserves the requirement and labels the code behavior as a gap. It recommends bounding the complete JEV call and routing expiry through the existing error handler if following the recorded short-deadline policy. Zero additional floor latency is a different interpretation and requires explicit accounting/distribution semantics. Neither changing prose alone nor deleting one flag suffices.

Two evidence corrections matter:

1. The confidence-in-author-feedback decision is attributed to **Claude**, not the owner (`element.md:94-97`). Current rules specify fixed owner feedback. GF2 therefore supports an explicit description reconciliation without requiring an owner to withdraw a promise that is not attributed to them.
2. `prompts::rejected(&failed)` receives numbers. A formatter can append those numbers to a fixed template without placeholders. Because `prompts.rs` is absent, turn.rs and the feedback templates do not prove that author confidences are omitted. We can accept the reviewer's report while labeling the exact rendering as not independently verified. By contrast, the floor Outcome withholding is directly visible in `resolve_reply`, even without engine.rs.

For a code fix, bounded completion is materially safer than a bare flag deletion: the existing error path removes the pending judgment, clears its floor barrier, accepts unjudged, and counts the floor opportunity. Releasing the floor early additionally changes when the opportunity is counted and whether acceptance belongs to a later round. The resolution names those obligations without claiming an implementation was made.

GF8 now explains why two budget scopes exist. GF10 is qualified because a directory pointer does locate the rubrics. GF12 retains the distinction between the auditability of message reasoning and retention of evaluator inputs; persisted outcomes and reproducible evaluation are different claims.
