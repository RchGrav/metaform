# Resolution of review findings — `code.rating.peer` (peer rating round)

Author: TotalLogic. Verified against the files present in `source/`: `crates/roundtable/src/turn.rs`,
`crates/roundtable/src/rules.rs`, `crates/roundtable-web/src/app.rs`, and the resource prompts.
Findings GF1 and GF6 cite `engine.rs`, `prompts.rs`, `config.rs`, `tables.rs`, and
`docs/owner-sources/roundtable-agent-ratings.md`, which are **not** in this folder, so those specific
line claims cannot be re-run here; I mark how far each is independently checkable.

## Verdict table

| Finding | Reviewer right? | Action |
|---|---|---|
| GF1 trigger/participants | Yes (partially verifiable) | Strengthen rules[0] |
| GF2 scoring rule | Yes — fully verified | Add scoring formula to rules |
| GF3 saving location | Yes — fully verified | Name host + storage in description |
| GF4 failure modes | Yes — fully verified | Add a failure-modes layer/note |
| GF5 messages/receipt | Yes — fully verified | Add receipt + results delivery to rules[1] |
| GF6 worker rubric in scoring prompt | Yes (rubric text present; provenance unverifyable) | Note the rubric in rules or reference |
| GF7 numbers unexplained | Yes | Explain weights/scale in description |
| GF8 identity undefined | Yes | Define/link identity + persistence caveat |
| GF9 wants vs rules mismatch | Yes | Clarify return payload vs recipient |
| GF10 'table' undefined | Yes | Define table and end conditions |
| GF11 references unnannotated | Yes (nit) | Add one-line note per reference |
| GF12 owner statement is a question | Partially — right that chain is unshown, but the resolution is already cited in `elephant.sources` | Add brief provenance |

## Detailed decisions

### GF1 — rules[0] trigger and participants: RIGHT
r0 says "When a table ends, each agent rates every other." That is false in two ways verified directly:
`start_rating` (turn.rs:420-434) is only reached from an End path, and it bails when fewer than two
seats are `Ready` **and** named (turn.rs:421-425) — it calls `self.end("ended by the chair")` and no
rating happens. Departed seats fail the `Ready` test and are excluded from `left`. A rater that cannot
be offered a prompt is silently completed via `rating_done(i)` (turn.rs:442-444). Missing ratings only
produce a notice (turn.rs:493-497), never a retry. **Change rules[0] to:** "When the chair ends a table
(and there are at least two ready, named seats), each such seat rates every other seat still present."
The specific engine.rs line numbers (last round, quiet-round, second-End, other ends) I cannot confirm
here, but the core overstatement is proven by turn.rs alone.

### GF2 — scoring missing: RIGHT (fully verified)
rules.rs:150-162 is exactly the described formula: stars `clamp(0,5)/5 * weight`, weights
Efficient 10 / Alert 20 / Thorough 30 / Coordination 40, plus `bonus` bool adding 5, max 105. `unwrap_or(0.0)`
means missing/non-numeric categories score 0 silently (rules.rs:158). turn.rs:529-544 sums session points,
sets rating = prior profile score + session points, else `"unscored"`. **Change:** the rules layer must
state the formula, the clamp, the silent-zero behavior, and that ranking is by summed (not averaged)
session points while `rating` includes prior history. Without this the rules describe inputs the reader
cannot turn into the published number.

### GF3 — saving is the host's job, not turn.rs: RIGHT (fully verified)
turn.rs only accumulates `session_points` and publishes `RatingGiven` (turn.rs:471-484). Persistence is
in app.rs: on `roundtable.rating` it calls `save_rating` writing `$ROUNDTABLE_HOME/identities/<session>.json`
(app.rs:98-102, 426-445, 498-509). `FileIdentities::profile` only reads (app.rs:478-495). **Change:** the
description should explicitly say the core computes and emits; the web host persists to the identity
file. Otherwise "saved to each agent's identity" is attributed to the wrong component. The
`tables.rs`/`spawn(None)`/engine.rs:255 claims I cannot verify here but are consistent with app.rs as sole
writer.

### GF4 — failure modes undocumented: RIGHT (fully verified)
turn.rs:450 takes JSON from first `{` to last `}`, so trailing prose passes and embedded braces can break
parsing. Unreadable JSON → notice, nothing recorded (turn.rs:487-491). Non-object card → rejected
(turn.rs:456-461). Name matching zero or >1 seats → not recorded (turn.rs:463-467) — so duplicate names
cannot rate each other; this is a real limitation. **Change:** add these to a failure-modes note; they are
observable behaviors an integrator must know.

### GF5 — messages omitted: RIGHT (fully verified)
turn.rs:498-501 offers `SCORE_RECEIVED` to a rater whose JSON was an object. turn.rs:37-50 prepends
`SESSION_PROFILE` to a returning identity's first turn. Results go only to seats that are `Ready`, named,
`Idle`, and not yet sent (turn.rs:551-560); the table ends when none remain waiting (turn.rs:563-575).
**Change rules[1]:** add the private `score_received` receipt, the returning-identity profile line, and
the condition that results reach only present, idle seats.

### GF6 — worker rubric: RIGHT as a description nit
`session_scoring.md:3-10` does contain the 4-row rubric table with "Give fewer stars for…" guidance.
Whether the owner's roundtable prompt quotes that table (docs/owner-sources...) I cannot check here, but
the description calling this "the owner's scoring prompt" while it contains extra worker guidance is a
real ambiguity. **Change:** one line in rules or references noting the scoring resource carries a worker
rubric table in addition to the terse roundtable instruction.

### GF7 — numbers unexplained: RIGHT
This is essentially the comprehension mirror of GF2. Since GF2 already requires stating the formula,
GF7 is resolved by the same edit: explain 10/20/30/40 as weights scaled by `stars/5`, bonus is a
boolean +5, one scorecard ranges 0–105. Do not fix GF7 separately; fixing GF2 covers it.

### GF8 — identity undefined/persistence caveat: RIGHT
The description says "saved to each agent's identity" but never defines identity, and `elephant.gaps`
admits ratings carry forward only if the session is resumed. app.rs shows identity = the genesis
session id, file-keyed (`profile_path`, app.rs:426-445). **Change:** define identity as the keyed profile
file and link `code.identity.agent`; state the resume caveat explicitly. This pairs with GF3.

### GF9 — wants vs rules mismatch: RIGHT
The manager's want is "return the results"; rules[1] says agents receive a message. Both are true but
different: the element returns results by publishing ranking/session events and by offering each seat
the `session_results` message. **Change:** state what "the results" are (per-seat points, card count,
cross-session rating, ranking) and that the manager consumes the returned data while agents receive the
message.

### GF10 — 'table' undefined: RIGHT
Nothing defines a table or what ends it. turn.rs shows end paths (`end("ended by the chair")`) but not
the full trigger set. **Change:** one sentence defining a table as the seats/discussion/rating instance
and noting it ends by chair End or the engine's limit/quiet rules (deferring exact triggers to
`code.manager` or engine if those aren't this element's scope).

### GF11 — references unnannotated: RIGHT (nit)
Each reference path needs a one-line "what this is": `session_scoring.md` = the rating prompt sent to
raters; `roundtable-agent-ratings.md` = the owner's source statement.

### GF12 — owner statement is a question: PARTIAL
The statement is indeed a question, and the description does not show how it became specific categories.
However `elephant.sources` already cites that owner line, and rules[0] attributes categories to the
owner. The reviewer is right that the derivation is unshown; the fix is a provenance note, not a code
change: say the categories came from the owner's earlier system (as rules.rs:150 comment states).

## Summary of required edits
1. rules[0]: rewrite trigger/participants (GF1); add scoring formula, clamp, silent-zero, ranking vs rating (GF2, GF7).
2. rules[1]: add `score_received`, `session_profile` line, results delivery conditions (GF5); name host persistence + identity definition + resume caveat (GF3, GF8, GF9).
3. Add failure-modes note (GF4) and reference annotations (GF11).
4. Define table (GF10) and note worker rubric / owner provenance (GF6, GF12).
