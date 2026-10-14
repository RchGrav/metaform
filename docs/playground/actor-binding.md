# Actor binding and the op-log record — cut 2's contract

MIN-13. Written before the verbs, because MIN-14's rig cannot be retrofitted onto a binding that
assumed a figure. It answers the six requirements in `docs/measurement/spatial-reference-protocol.md`
§6 one at a time, says where the repo as it stands does not already allow them, and corrects two
that name something Metaform does not have.

Nothing here adds a second code path. `B0` and `B1` are one implementation, one op log, and the
difference between them is whether an animation is scheduled after a record is committed.

## 1. Binding is a noun on the call

Today the caller is implicit. `ask_page` reads `METAFORM_WORK` and `METAFORM_ROLE` out of the
process environment (`src/metaform/modules/web/__init__.py:595`) and `web_embody` asks the page for
a body, which the page then keeps as state (`:806`). A harness alternating arms against one scene
would have to mutate its own environment between trials, and the body would still be world state.

Cut 2's verbs take `actor` as a noun:

- `actor=<body id>` — that body acts.
- `actor=none` — the null binding. Legal, explicit, and not the same as omitting it.
- omitted — the body bound to this session (`shown.session()`, `src/metaform/shown.py:46`), else the
  person's mascot.

World state keeps the *default* and never the *decision*. Switching arms is one noun on the next
call: no world rebuild, no re-embodiment, no environment write. (Requirement 1 of §6, requirement 2
of the comment.)

`actor=none` on a verb that moves the agent's own figure — the cut-1 locomotion verbs — is refused
with `refusal.kind=invalid`, because there is nothing to move. The five cut-2 verbs
(`see`, `hold`, `place`, `drop`, `throw`) all accept it.

## 2. Resolution reads the view frame, never the actor's transform

This is the load-bearing consequence of requirement 3, and it is stronger than "use a second RNG
stream". A separate stream is necessary and not sufficient: if `hold` resolved "the crate nearest
the actor", then `B0` and `B1` would differ in *clutter* and *attention* with no random draw
involved at all, because the walk changes what "nearest" means.

So the geometry a verb resolves against is the **observation's view frame** — the camera transform,
the pointer ray and the raycast hit that went out with the observation — not the body's pose. Where
a tie-break genuinely needs a position (two candidates equally consistent with the deictic), it uses
the view frame's origin. Under `actor=none` the view frame is whatever the observation carried, so
the same instruction over the same observation resolves the same entity id and the same contact
point in both arms.

That is the invariant the implementation has to carry a test for: same seed, same scene, same verb
sequence, `B0` and `B1` resolve identical entity ids and identical contact points, and the world
stream's draw count is equal at the end of both.

## 3. Two named streams from the tick seed

The world host derives, from the tick seed and nothing else:

- `world` — physics jitter, scene generation, settling tie-breaks. Advances only on committed
  op-log records and on world steps.
- `motion` — gait phase, reach noise, animation easing. Per actor, derived from
  `(seed, actor id)`, and drawn **only** by the walk and the animation.

A null binding never constructs a `motion` stream, and an embodied one never draws from `world` for
its walk. Requirement 1 of the comment, held structurally rather than by care.

## 4. One path: resolve → validate → commit → animate

The verb body is one function in that order. The body is a *consumer* of a committed record, not a
precondition for it. `B0` omits the last step and nothing else, so it cannot be cheaper for the
wrong reason. (Requirement 4.)

The one asymmetry worth naming, because it is where a skipped check would hide: **reach**. If an
embodied actor must stand within reach before it grasps, and a null actor has no stand, then either
`B0` skips the check or `B1` fails where `B0` succeeds. Neither is acceptable, so reach is validated
from the **view frame origin** against the same radius in both arms. What differs is only whether a
walk is scheduled to satisfy it. When the walk cannot satisfy it, both arms refuse with the same
`refusal.kind=unreachable`, and the refusal is a record in both.

## 5. The record

Every op-log record carries, beyond cut 1's user, agent and world ids and its `functional_refs`:

| field | what it holds |
|-------|---------------|
| `actor` | body id, or null |
| `actor_source` | `given`, `session` or `mascot` — so a disputed trial shows whether a null was declared or inherited |
| `at_wall` | monotonic nanoseconds with a wall anchor |
| `at_sim` | tick index and simulated seconds |
| `session` | `shown.session()` — the runner token the call was made under. Not a `spend` key; see below |
| `acp_session` | the ACP session id, resolved at commit. This is the `spend` join key |
| `work`, `run` | the ticket and run, as dispatch names them |
| `spend_seq_before`, `spend_seq_after` | dispatch usage watermarks, read at verb entry and return. Ordering within a trial, not a usage window |

and, on a committing verb (`hold`, `place`, `throw`):

| field | what it holds |
|-------|---------------|
| `resolved.entity` | the entity id the verb acted on |
| `resolved.candidates` | the ids that survived to the tie-break |
| `resolved.rule` | which rule resolved it — name, relation, pointer cone, hit |
| `contact.point`, `contact.normal`, `contact.entity`, `contact.feature` | the contact, in world units with the frame named, per the roundtable's recommendation 3 |

and, on a refusal:

| field | what it holds |
|-------|---------------|
| `refusal.kind` | one of `ambiguous`, `clarify`, `unreachable`, `unsupported`, `leased`, `invalid` |
| `refusal.candidates` | for `ambiguous` and `clarify`, what it could not choose between |

`ambiguous` (more than one candidate survived, the verb declined) and `clarify` (the agent asked the
person which one) are distinct values and neither is mixed with the other four, so metric 3 can
count both and still tell them apart. (Requirement 5.)

### Corrections to §6.5, and to this section's first revision

**There is no provider turn id to give you.** Dispatch's usage rows are the `spend` table, keyed
`(session_id, seq)`, with `work_id`, `run`, `day`, per-kind counts and `metered`
(`src/metaform/modules/dispatch/__init__.py:145`). Nothing in it holds a provider-side turn
identifier, and inventing one here would mean a field that is only ever filled by my own
bookkeeping — which is the thing requirement 3 exists to avoid. Instead the record carries the
session plus the two `spend_seq` watermarks above.

**A trial's usage is every `spend` row of that trial's session** — the whole session, not a `seq`
window. An earlier revision of this section named the window `(before, after]` as the rule, and
MIN-14 is right that it is wrong: both watermarks are read mid-turn, at verb entry and verb return,
while `spend()` writes the turn's token row when the agent reports usage as the turn closes
(`src/metaform/modules/dispatch/runner.py:1765`). A single-verb trial's window therefore holds zero
token rows — it misses the one turn that did the work, and reads as free rather than as an error.
`cost_spent()` writes separately, a row per usage update with `tokens: 0` (`:1800`), so tokens and
cost land on different rows at different times and any sub-session window splits one trial's cost
across two. The watermarks stay in the record, for ordering verbs within a trial; they are not the
usage join. One agent session per trial is the rig's obligation, recorded as requirement 8 of the
protocol. `metered=false` rows sit inside the session like any other, so unmetered turns stay
visible, which is the property the window was there to protect.

### The session field is not the spend key

The join needs one more thing than requirement 8 assumes, and it fails in the same silent direction.
`shown.session()` returns `METAFORM_SESSION` (`src/metaform/shown.py:46`), which dispatch sets to
`self.runner`, a token it mints per launch (`runner.py:2758`). `spend.session_id` is the **ACP**
session id the agent returns (`:2693`). They are different identifiers. Reading `spend` by
`shown.session()` matches no rows at all — zero cost, no error, exactly the failure mode being
corrected.

The `sessions` table holds both (`session_id` key, `runner` column,
`src/metaform/modules/dispatch/__init__.py:91`), so the hop is available. The world host makes it at
commit and records `acp_session`, rather than leaving the rig to join later, because a resume
rewrites `runner` on the same `sessions` row (`runner.py:2833`): after a second resume, a historical
runner token is in no row and the lookup silently finds nothing. Resolved at commit, it is pinned.

`run` is the join to prefer when a trial's session was retried — a retry spends against the run of
the session it resumes (`runner.py:1066`), so `run` covers a session and its retries, and `spend` is
indexed on it. `acp_session` is the narrower key; `run` is the one that does not lose a retried
trial's tokens.

**Intended referent stays out of the op log.** §6.5 asks for "intended-vs-resolved on the committing
verb". The world records `resolved`; `intended_referent` is the scene's declared data (§2 of the
protocol) and the rig joins the two. Two reasons: a world that knows the intended answer is a world
that can grade itself, and an observation payload that holds the answer can leak it to the model.
The comparison is yours to compute; both halves of it are reproducible from the record and the scene
declaration.

## 6. Resetting between trials without a rebuild

Requirement 2 wants one scene instance across arms, and a trial leaves the world moved — the crate
is on the table and `B1`'s figure is standing beside it. So the pairing needs a reset that is not a
rebuild: the world host takes `restore(tick)`, which replays the op log to a checkpoint inside the
same instance and discards what follows. Scene generation does not re-run, so its variance never
enters the body contrast, which is the whole point of pairing.

It is the same primitive MIN-29's stepped replay needs, so it is not built for the rig alone.

## 7. Overlays and the agent's camera

Accepted, and implemented as a render rule rather than a per-call flag, because a flag is a thing
someone forgets. Agent frames render from an **allowlist** of layers held in one constant in the
world host. Ghosts, view cones, gaze, the tether, selection markers, labels and edge arrows are
person-facing layers and live in a scene the agent camera never renders — so there is no code path
that leaks one into an agent frame, and `I` and `I+R` stay clean. The pointer ray is the only
overlay an agent frame can carry, it is drawn only when the call asks for it, and when it is drawn
it is named in the frame's legend, per the roundtable's recommendation 7.

Note that `web_capture source=view` does the opposite on purpose: it is the person's own 3D view
with the pointer's ray drawn in (`src/metaform/modules/web/__init__.py:740`). It is the person's
frame, not the agent's.

### One thing for the protocol's side

Render `I+P` from the **agent's own camera** with the pointer-ray layer added — not from
`web_capture`. If `I+P` came from the person's view, then at `B1` the agent's figure would be
standing in the frame and at `B0` it would not, so axis B would leak into exactly the one modality
cell where an overlay is the condition. Agent frames exclude the actor's own figure from the render,
so no body appears in its own frame, and `I+P × B0` and `I+P × B1` differ only in whether a walk
happened. If you want a person's-view condition as well, that is a fifth modality level and
`web_capture` already produces it.

## Status

Blocked on MIN-12 for the op log this writes to. The schema above is what MIN-12 needs to carry from
the first migration — `actor`, `actor_source`, the two clocks, `session`, `acp_session`, `run` and
the spend watermarks — because adding them after records exist means a migration and a re-run of
anything already measured. `acp_session` is the one added by this revision, and it is the one that
cannot be reconstructed later: the runner token it resolves from is overwritten on resume.
