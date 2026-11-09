# SpinedSolid addendum to resolution.md (self-correction)

Filed after re-reading `source/crates/roundtable/src/engine.rs:1-50, 500-539`.

## 1. Floor definition in GF7/GF10 was too narrow — correct to two conditions

My resolution defined "floor" as only a pending JEV verdict. That is wrong.

From code:
- `engine.rs:10`: "The floor is offered only while at least two participants are free"
- `engine.rs:157,161-164`: `floor: Option<(usize,u64)>` is whose turn it is; `judging_floor: Option<u64>` is a floor contribution awaiting JEV, so the next turn waits.
- `engine.rs:511-513`: the engine returns early (does not apply a stored advance) while `self.floor.is_some() || self.judging_floor.is_some()`, then at 511-519 applies `advance` only after that check.
- `engine.rs:41,872`: "End the current topic once the floor is free" / "applied when the floor is free".

Therefore "floor free" means BOTH:
1. `floor` is None — no participant currently holds the speaking turn, and
2. `judging_floor` is None — no floor contribution is awaiting a JEV verdict (RT-G10).

"Floor" itself is the speaking turn offered to a participant (seat order, at least two free participants required, `MIN_FREE_TO_DISCUSS=2`, line 30). This corrects resolution.md GF7 and GF10. The recommended D fix for GF7 stands, with this exact definition inserted.

## 2. GF12: TRACEABILITY is locatable in principle — downgrade half

`engine.rs:3-4` states: "Every rule here traces to `docs/TRACEABILITY.md` (R = README.md, D = the ACP integration design, O = an owner decision)". So TRACEABILITY is a real repo document, R/D/O are defined prefixes, and the elephant's "(TRACEABILITY I-3, I-4)" points into it. It was not copied into the review folder, so I could not verify I-3/I-4 contents — the citation is unverifiable *from the materials supplied*, not necessarily unlocatable in the repo.

Corrected verdict for GF12:
- TRACEABILITY I-3, I-4: PARTLY RIGHT. Not a bogus citation (document and prefix scheme are attested in engine.rs:3-4), but the specific items cannot be checked without docs/TRACEABILITY.md. Fix: copy/point to the file in the review bundle (or quote I-3/I-4), do not invent their content.
- "ACP v2 workspace/tool distinction": still RIGHT as a nit — no section number is given, unlike e.g. "D §6" in engine.rs:7 which shows the project does cite section numbers elsewhere. Add the § number.
- Claude-only decision status: RIGHT, unchanged. Mark status (implemented vs owner-ratified) against the owner's open feedback question.

## 3. No other change

GF1-GF6, GF8-GF11 verdicts in resolution.md stand. In particular GF4's stored-advance semantics are now pinned to engine.rs:511-519 + 873-879: stored on Command::Advance, applied on a later pass of the same function only when neither floor nor judging_floor is pending and topics are active, silently replacing any prior stored advance (879, no displacement notice).
