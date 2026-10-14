# Spatial reference measurement — protocol

MIN-14. Pre-registered before any run, because the result is a product finding and a protocol
settled after seeing numbers is not a finding. Thresholds marked **proposed** are open to the
founder until the first run; after it they are fixed.

Answers two questions that the first roundtable left open (`docs/roundtables/1-embodied-ai-in-a-3d-physics.md`):

- §5 *How much the agent should see* — pixels against structured state. Does the structured ray
  and entity identity earn its complexity over an image with a pointer overlay?
- §5 and §6.12 *Whether a body is needed at all* — Opus asked for matched trials against a
  tool-only agent (T17, T380, T391); Gemini's catalogue assumed a body throughout; nobody
  reconciled them.

## 1. Two axes, not one

The four conditions in the issue are one axis. Body is a second axis, and the two confound if
only the first is named: a figure in the frame **is** an overlay, so `image + overlay` silently
becomes `image + overlay + body` and no reading of the embodiment question survives.

**Axis A — reference modality** (the issue's 4 levels, plus a shipped baseline costed in §4)

| id | level | payload the model receives |
|----|-------|---------------------------|
| `T` | text only | visible-entity list, no frame |
| `I` | image only | rendered view |
| `I+P` | image + pointer overlay | the **agent's own camera**, pointer-ray layer added |
| `I+R` | image + structured ray and identity | rendered view, camera transform, pointer ray, raycast hit entity, contact point |
| `I+V` | person's view + their pointer | `web_capture source=view` — the status quo, see §4 |

These map onto MIN-13's declared observation payload exactly
(`docs/playground/actor-binding.md` §5), so no condition needs a field the world host is not
already producing.

`I+P` renders from the agent's camera, not `web_capture`, on MIN-13's correction. The person's
view with their pointer drawn in also contains the agent's figure at `B1` and not at `B0`, so it
leaks axis B into the one modality cell where the overlay *is* the condition. Agent frames exclude
the actor's own figure, so `I+P × B0` and `I+P × B1` differ only in whether a walk happened.
`I+V` is that person's-view frame kept as a separate level rather than smuggled into `I+P`.

**Axis B — body** (2 levels)

| id | level | binding |
|----|-------|---------|
| `B1` | embodied | a figure bound as the actor on the call |
| `B0` | tool only | a null body, legal binding, same verbs, no walk and no animation |

Per MIN-13 both arms come out of one implementation and one op log, so the marginal engineering
cost of axis B is zero. Only model calls double, and §4 bounds where.

## 2. Scene grid

Five classes. Difficulty is set by named knobs, not by judgement, so a scene regenerates
identically from its seed.

| class | referent is found by | easy → very hard knob |
|-------|---------------------|-----------------------|
| `unique` | its own name; no competitor | 1 → 4 unrelated entities in view |
| `clutter` | relation among near-identical siblings | 2 → 8 siblings, and sibling similarity from differing-colour to identical |
| `search` | leaving the initial view to find it | referent 30° → 180° off initial heading, 0 → 2 occluders on the path |
| `attention` | a deictic the person indicates — "that one" | 1 → 4 plausible candidates inside the pointer cone |
| `occlusion` | partial visibility | referent 0% → 80% hidden behind another entity |

Four grades per class — easy, moderate, hard, very hard — so 20 scenes. `clutter` at hard is the
acceptance scene from MIN-7 and MIN-13 (three similar crates and a table), which is deliberate:
that scene then carries a measurement as well as a pass or fail.

Each scene declares, as data the rig reads and never infers:

- `intended_referent` — the entity id a correct reading resolves to
- `intended_hit` — the point on it a correct placement or grasp lands on
- `movable_without_penalty` — entity ids that may legitimately move on the way to the goal
- `seed` — the tick seed the world replays from

## 3. Metrics

Six, as the issue specifies, each with its source field and the form it is reported in.

1. **Referent-selection accuracy.** Fraction of trials where `resolved.entity` on the first
   committing verb (`hold`, `place`, `throw`) equals the scene's `intended_referent`. Binary per
   trial, read from the op log. Never from the agent's own account of what it picked. The join is
   the rig's: `intended_referent` stays out of the op log on MIN-13's second correction, and that
   is right — an observation payload holding the answer can leak it to the model.
2. **Distance from intended hit.** Metres between `contact.point` and `intended_hit`. Reported as
   **median and 90th percentile**, not mean: one tunnelled grasp otherwise owns the average.
3. **Clarification rate.** Per trial, the count of records with `refusal.kind` in
   (`ambiguous`, `clarify`) — the verb declining between surviving candidates, and the agent asking
   the person which one. Reported summed **and split**, because they are distinct values in the
   record: a condition that refuses instead of asking has not avoided the cost, but it has moved it.
4. **Wrong-edit rate.** Two variants, both reported, because §5 never settled what counts as
   success. **Strict**: any entity other than the referent whose transform changed beyond
   tolerance (Kimi T37, "nothing else moved"). **Intent-scoped**: the same, less the scene's
   `movable_without_penalty` list (Astra T45, opening a drawer to reach a cup is progress). Scored
   off the declared list, not a model judge, so the number is reproducible. Physics settling below
   tolerance is excluded; engine artefacts named in §1 of the roundtable report — tunnelling,
   waking bodies, warm-started impulses — are logged as world faults and excluded from the
   agent's score, counted separately.
5. **Time to action.** Two clocks, and reporting only one would make the body comparison
   meaningless. **Wall clock** from instruction delivery to the committing verb's record — this is
   where model latency lands. **Simulated time** over the same span — this is where the walk
   lands, because the world waits while the agent thinks (Fable T19). A body costs sim time and
   may cost no wall time at all.
6. **Model calls.** Input, output, cache-read and cache-write tokens, their `billable()` sum,
   reported cost by currency, and images sent — joined from dispatch's `spend` table
   (`src/metaform/modules/dispatch/__init__.py:145`). There is no provider turn id to key on;
   MIN-13's first correction is accepted and the metric names the join instead.

   **The join is one session per trial, not a watermark window.** A trial gets its own agent
   session, and its usage is every `spend` row of that session. **The field to join on is
   `acp_session`, or `run`; never `session`.** `session` is `shown.session()`, the runner token
   dispatch mints per launch (`shown.py:46`, set from `self.runner` at `runner.py:2758`), while
   both `spend` writers key their row on `self.session_id`, the ACP id the agent returns
   (`runner.py:1781` and `:1828`, bound at `:2693`). Joining `spend` on the field named `session`
   matches **zero rows** and reads as free — stated here at the field, because whoever implements
   the scorer will read "session id" and reach for the one named `session`. MIN-13 resolves
   `acp_session` through the `sessions` table at commit time (`dispatch/__init__.py:91`) rather
   than leaving the lookup to the rig, since a resume rewrites `runner` on that row
   (`runner.py:2833`) and a twice-resumed token is then in no row at all. Choice of key: §6.8.

   The per-record `spend_seq_before` / `spend_seq_after` watermarks stay in the record and are used
   for ordering *within* a trial, but they cannot be the unit of this metric, for two reasons read
   off the writer rather than assumed:

   - **Token rows land at turn end.** `spend()` inserts a turn's token row when the agent reports
     usage as the turn closes (`runner.py:1781`). A verb's watermarks are both read mid-turn, so
     `(before, after]` on a single-verb trial contains **zero** token rows. The watermark window
     misses the one turn that did the work.
   - **Cost rows land mid-turn.** `cost_spent()` inserts a separate row per usage update, with
     `tokens: 0` (`runner.py:1828`). Tokens and cost therefore arrive on different rows at
     different times. Any window narrower than the session attributes the two halves of a trial's
     cost to different trials.

   `seq` is `time.time_ns()`, so both are exact under a session-scoped join and need no clock
   reconciliation. A trial whose turn comes back **unmetered** (`metered=false`, the provider
   reported no usage) is counted and named, never averaged in as zero — those rows sit inside the
   session like any other, which is the property that makes this join honest. Images sent is
   reported on its own line: the image conditions can win on accuracy and lose on cost, and that
   trade is the point.

Metrics 3 and 5 are the two I expect to move with the body rather than with modality, which
matches the playground's reading.

## 4. Cells actually run, and what is dropped

Pairing: for one `(scene, seed)` every cell runs against **the same scene instance**. Scene
generation variance therefore does not enter either contrast. This is Opus's matched trials.

Axis B is crossed on the three classes §6.12 named — clutter, search, attention — where the table
expected a body to win if it wins anywhere. It is held at `B1` on `unique` and `occlusion`.

| set | classes | cells | scenes | runs per seed |
|-----|---------|-------|--------|---------------|
| body-sensitive | clutter, search, attention | 4 modality × 2 body = 8 | 12 | 96 |
| modality-only | unique, occlusion | 4 modality × `B1` = 4 | 8 | 32 |
| status quo | attention | `I+V` × `B1` = 1 | 4 | 4 |

132 runs per seed, 3 seeds, **396 runs** for a full pass. The cut knob is seeds, then the
modality-only set.

`I+V` is held at `B1` on `attention` alone, and is deliberately **not** part of either contrast.
It is there because `web_capture source=view` is what an agent gets *today* when it asks what the
person is pointing at (`src/metaform/modules/web/__init__.py:740`), so it is the shipped baseline
the new work has to beat, and `attention` is the only class where a person's deictic is the
referent. It carries the body confound by construction — the agent's figure stands in the person's
frame — which is exactly why no `B0` arm is run against it and no body claim is read off it. 4
runs per seed to know whether the thing being built beats the thing already shipped.

**Dropped, stated rather than left implicit:** `unique` and `occlusion` are not tested without a
body. If the body turns out to help there, this protocol will not see it. The cost of adding them
is 32 runs per seed and the decision is reversible.

Two cell pairs carry the §6.12 answer between them, and they are the reason the full cross is
worth its cost:

- **`T` × `B0`/`B1` isolates the body's cost.** Text only has no pixels, so a figure cannot appear
  in frame and the pixel confound is gone entirely. Anything that moves here is the walk.
- **`I+R` × `B0`/`B1` isolates the body's benefit**, at the richest modality, which is where the
  table expected it.

## 5. Decision rules, pre-registered

**Proposed**, pending the founder, and fixed once the first run starts.

**The body earns its place in a scene class** when, at `I+R`, it either raises referent accuracy
by ≥10 points or lowers clarification rate by ≥0.25 per trial; the direction holds on at least 2
of 3 seeds; and it costs no more than 2× simulated time to action and no more than 1.25× model
calls. Where it does not clear that bar, the recommendation is to keep the body offered and not
imposed, per §6.12 — "keep the body where it wins".

**The structured ray and entity identity earn their complexity** when `I+R` beats `I+P` on
referent accuracy by ≥10 points, or matches it on accuracy while sending fewer images.

If `I+R` does not clear that bar, the finding goes to the founder as a product finding, not a test
failure, and this document records the comparison that produced it including the uncomfortable
form. The same applies to the body: a null result on axis B is a reportable answer to a question
the table could not settle, not a gap in the rig.

## 6. What the rig needs from upstream

All six requirements were answered on MIN-13 and are written down as cut 2's contract in
`docs/playground/actor-binding.md`. What follows is the settled form, so the rig is built against
one document and not against a thread. Two were corrected in the answering and the corrections
stand; the record for the rest is MIN-13's, not mine.

1. **Body binding is per call, not world state.** `actor=<id>` / `actor=none` / omitted, as a noun
   on the verb (§1). Switching arms is one noun on the next call — no world rebuild, no
   re-embodiment, no environment write.
2. **Every op-log record carries its actor binding explicitly**, plus `actor_source`
   (`given` / `session` / `mascot`), which I did not ask for and should have. `actor: null` alone
   cannot distinguish a declared `B0` from a session that simply had no body bound, and arm
   attribution must not have to assume. Taken.
3. **The body does not perturb resolution.** Answered more strongly than asked: resolution reads
   the **observation's view frame** — camera transform, pointer ray, raycast hit — never the body's
   pose, and position tie-breaks use the view frame origin (§2). Named `world` and `motion` streams
   off the tick seed keep the draw counts equal (§3). My requirement would have been satisfied by
   a second RNG stream and would still have been wrong: a proximity rule splits `B0` from `B1` in
   clutter and attention with no random draw involved.
4. **The null binding runs the same validation.** Reach is validated from the view frame origin
   against the same radius in both arms; only the walk that satisfies it differs, and an
   unsatisfiable reach refuses as `unreachable` in both, as a record in both (§4).
5. **Records by name:** `resolved.entity`, `resolved.candidates`, `resolved.rule`, `contact.*`,
   `refusal.kind` with `ambiguous` and `clarify` distinct, `at_wall` and `at_sim`, `session`,
   `acp_session`, `work`, `run` (§5). `acp_session` was added in MIN-13's second revision and is
   the one metric 6 joins on. Two of my asks were refused correctly — there are no provider turn ids to
   carry, and `intended_referent` stays out of the op log so the world cannot grade itself. Both
   are absorbed into metric 6 and metric 1 above.
6. **Overlays stay off the agent's camera** except in `I+P`. Implemented as a layer allowlist in
   the world host rather than a per-call flag, so person-facing layers — ghosts, view cones, gaze,
   tether, selection markers, labels, edge arrows — have no code path into an agent frame (§7).
   Stronger than the requirement, which a forgotten flag would have satisfied on paper.
7. **Pairing needs `restore(tick)`, not a rebuild.** A trial leaves the world moved, so one scene
   instance across arms means replaying the op log to a checkpoint inside the instance (§6).
   Shared with MIN-29's stepped replay.
8. **One agent session per trial, and one `run` per trial** — the rig's own obligations, recorded
   here because metric 6 depends on both. No concurrent turns in a trial's session, and no other
   work in it.

   The join field is `acp_session`, or `run`, and never `session` (metric 6). **The rig passes
   `run=<trial id>` on every launch of a trial, including any retry it drives itself**, and then
   joins on `run`. This is a rig obligation and not a property of the system, because `run` is
   trial-scoped only if the rig makes it so. Two mechanisms, both read off the writer:

   - **`run` defaults to per-process, not per-trial.** `run_id` is `nouns.get('run') or RUN`
     (`runner.py:1066`), and `RUN` is one `token_hex(8)` per interpreter (`:152`). A supervisor
     that launches many trials in one process without the noun gives them all one `run`, and the
     join then **over**counts by the whole pass.
   - **Inherited `run` does not survive an unmetered first attempt.** The supervisor's own retry
     inherits the run by reading the retried session's latest `spend` row
     (`run_of`, `dispatch/__init__.py:1652`, `:1781`). That returns `None` when the first attempt
     wrote no row — it died before a turn closed, or the provider reported nothing — and the retry
     is spawned with no `run=` and mints a fresh one. A scorer that captured `run` at trial start
     then finds the first attempt's zero rows and **misses the retry's entire spend**. Passing the
     noun explicitly removes the inheritance step, so `run` spans a trial's attempts
     unconditionally rather than only when the first one spent.

   `acp_session` stays the narrower key and is what a single-attempt trial joins on; `run` is the
   one that does not lose a retried trial. Both are on the record, so a pass can be re-scored under
   either and the two compared — a trial where they disagree is a trial that was retried.

Remaining upstream dependency is MIN-12's first op-log migration, which has to carry `actor`,
`actor_source`, both clocks, `session`, `acp_session`, `work`, `run` and the spend watermarks from
the start: adding them after records exist means a migration and a re-run of anything already
measured.

## 7. How it runs

On demand, never in the default matrix: these trials cost model calls. Marked
`@pytest.mark.kind('simulation')` per the repo's rule that every test names its kind of run, with
the mocked-provider arm under `kind('fixture')` so the rig's own plumbing — scene generation,
seeding, metric computation off recorded op logs — stays green in CI at no provider cost.
Fixtures extend the existing `conftest.py` (`home`, `run`, `project_folder`, `store`) rather than
standing up a second harness.

The rig is scored off recorded op logs, so a run can be re-scored without re-running it. When
MIN-29's stepped replay lands, a disputed trial can be opened at the decision in question and the
exact observation the model received read off the record.
