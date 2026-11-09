# FangedMercy — the converged D-W10 design cannot handle create tasks (and how to fix it)

Target: `scalyhornet-final-consensus.md` (lockable). I am NOT reopening the
selection rule (fixpoint, sink/through/consumer, bidirectionality), the delivery
frame, or the budget. Those are converged and I accept them. I am pointing out a
case the locked design has no branch for, giving a concrete falsifiable failure,
and a minimal addition that reuses the converged machinery.

## The gap, stated as a causal chain

The consensus seeds selection with: "all entities named in the task (resolve via
entity index; ambiguous -> ask, never dump)". Every subsequent step — the
bidirectional fixpoint, sink/through/consumer classification, `unmet_ports[]`,
the declared/observed/requested distinction — is a walk over entities that
ALREADY EXIST in the world graph, with ports, links, joints, handles and intent
records.

But the spec's primary workflow is the opposite. W-5.5: "A user records intent
for how an entity works. An agent builds the entity from that intent." W-11.3:
"A world is a development environment. Users and agents build and test in it."
W-12.1/W-12.2: the success criteria are built from the void as content. The
brief's own example task is "build a door that opens when a lever is pulled" —
a BUILD verb, not a MODIFY verb.

For such a task, at task start, in a fresh region or the admin void (W-9.1):
- there is no `door` entity and no `lever` entity in the entity index;
- there are no ports, no links, no joints, no granted handles, no W-5.5 intent
  records attached to those objects (the intent is written against the task, not
  yet against an entity).

Apply the locked algorithm step by step:
1. Seed: resolve "door" and "lever" via entity index -> ZERO matches.
2. The consensus handles "ambiguous" (many matches) but has NO branch for
   "zero matches". The nearest existing behaviour ("ambiguous -> ask") would
   emit "which door?". That is the wrong answer: the correct interpretation is
   "create one", not "disambiguate among existing ones".
3. Fixpoint expansion: no seeds -> no inbound ports -> no unmet goals -> empty
   set. `unmet_ports[]` is empty because no ports exist to be unmet.
4. Packet: empty, or a spurious disambiguation question. The agent receives
   none of the three things W-5.6 says context must supply ("the objects the
   task involves, how they connect, and what each one is meant to do").

BluntDiode got closest: "Objects requested but not yet built should appear as
creation requirements, without invented IDs", and the consensus carries
`unmet_ports[]` = "the build plan" and "objects to create". But those are
RENDERING fields. The SELECTION machinery still has nothing to select from, so
for a pure create task those fields are populated from thin air. The design
answers "which existing facts does the agent need?" and the game's main task is
"build a new object from intent".

## What would show me mistaken

If the owner confirms either: (a) agents are only ever assigned tasks against
pre-existing scaffold entities that already carry manifests and intent records,
so every task resolves to >=1 seed; or (b) the world pre-populates placeholder
entities (with ports and intent records) for every object a player might ask an
agent to build. Under (a) or (b) the zero-match case never arises and no create
class is needed. Neither is in the spec; W-2.1 (void: no items, no rules) and
W-2.3 (void world: no chunk data) point the other way.

## Minimal fix: a create class that precedes the fixpoint, reusing converged parts

Do not add a second resolver. Add one classifier and one selection source, then
let the converged graph_seq staleness mechanism hand off to the existing fixpoint.

### Classifier (deterministic, server-cheap, structural-only)

A task is `create` iff BOTH:
- its main verb denotes construction (`build`, `make`, `add`, `place`, `create`),
  read from a fixed verb list — no NLP / TF-IDF, preserving DirectCobalt's
  structural-only, O(bound) lock; AND
- the entity index returns ZERO exact matches for a named role within the
  task's scope.

Otherwise `modify` (existing consensus rule). Many matches -> ask (existing
rule). So: zero+build -> create; zero+non-build -> `unmet_ports[]` + question;
one-or-more -> fixpoint. Three locally-checkable branches, no scoring.

### Selection for `create` (signature retrieval, not graph traversal)

1. Seed = the W-5.5 intent record the user just wrote, verbatim, one sentence.
   This is the ONLY artifact that exists at task start.
2. Reuse LinkedPower's own subject/trigger/condition shaper to turn the intent
   into role -> port-signature pairs: subject=door (inbound bool, joint motor
   actuator), trigger=lever (`use` inbound per W-7.5, outbound bool),
   condition=pulled -> open. No new parser.
3. The "chosen from the world" step: a typed lookup over released ASSEMBLIES
   (W-9.4) — assemblies hold manifests, so they are the world's library of
   reusable port signatures. Retrieve top-k whose signatures match the roles by
   WIT type. Emit signatures + one-line descriptions, NOT internals. This is the
   create-side analogue of the fixpoint's typed link following, and it reuses
   W-5.4's type discipline instead of inventing a relevance score.
4. Emit the minimal host-interface capabilities needed (W-7.2: ports,
   actuators/joint motors) and the handle grants the agent must obtain (W-7.4)
   before it can drive the door motor — the same handle-scope safety the
   consensus already requires on actuators, applied before the entity exists.
5. Emit absence facts ("no entity named door in scope") and `create_requirements`
   (BluntDiode's creation requirements without invented IDs), folded into
   `unmet_ports[]` so the build plan stays explicit. No entity IDs are invented.

### Handoff (reuses converged staleness, adds no parallel path)

As the agent builds, every new entity/link is a `graph_seq` change. On the first
change the classifier re-runs: zero-match becomes one-or-more, so the tour
switches from create-scaffold to the `modify` fixpoint over the now-existing
subgraph — same `tour_id`, same `graph_seq` push-on-change one-liner, same
declared/observed/requested rendering. One tour, two phases, one staleness
mechanism. This is why the fix is an addition to the consensus, not a rival
resolver.

## Falsifiable checks (same style as LinkedPower / BluntDiode)

- C1 (empty-scope create): "build a door that opens when a lever is pulled" in
  a void region -> packet contains the intent, role signatures, host
  capabilities, `create_requirements`, and NO invented entity IDs; it must NOT
  return "which door?". FAILS if absence is misread as ambiguity, or if the
  packet is empty.
- C2 (phase switch): the SAME task, but a door entity now exists -> classifier
  flips to `modify`, packet is the fixpoint output (sink/through/consumer), not
  the scaffold. FAILS if there is no class switch or both phases render at once.
- C3 (create-side type check): two released assemblies match the "lever" role
  but expose bool and f32 outputs -> surface the type mismatch as a CHOICE, not
  a silent pick. FAILS if retrieval picks arbitrarily. This is W-5.4's type
  check applied to blueprint reuse.

## Net effect on the answer to D-W10

Selection is no longer one rule but a two-phase classifier:
- create (nothing exists): select from intent + typed assembly signatures +
  host capabilities; short by construction because links/joints/handles do not
  exist yet to be included.
- modify (entities exist): the converged bidirectional fixpoint.
Both feed ONE budgeted, push+pull, staleness-guarded packet. This covers W-5.6
("the objects the task involves, how they connect, and what each one is meant to
do") for the build-from-intent workflow that W-5.5, W-11.3 and W-12.1/12.2 put
at the centre of the game, which the locked design otherwise leaves unhandled.
