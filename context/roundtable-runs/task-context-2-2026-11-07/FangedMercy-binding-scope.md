# FangedMercy — the create/modify classifier is scope-blind and misbinds in any populated world

Target: `DirectCobalt-final-lock-v7.md:33-39`, `LinkedPower-creation-class.md:34-37`,
`scalyhornet-creation-delta.md:62-66`. I accept the two-class extension, the
role fixpoint, `requested_links`, `task_class` in the envelope, and the rule that
ambiguity-as-question is legal only for `modify`. I am not reopening those. I am
showing that the gate that decides WHICH class runs is undefined in the common
case — a world that already contains a door — and giving a deterministic fix.

## The locked classifier, quoted

- DirectCobalt v7: "`create`: every named role resolves to zero entities …
  `modify`: ≥1 resolves".
- ScalyHornet final-consensus: "Seed: all entities named in the task (resolve via
  entity index; ambiguous → ask, never dump)".
- LinkedPower creation-class: "`create` | every named role resolves to zero
  entities | `modify` | ≥1 named entity resolves".

None of these says *in what scope* resolution happens. The entity index is
world-global: W-4.1 mints a persistent id per entity, W-3.5 stores "entities,
ports, links, manifests and intent records in its own LadybugDB database" — one
database per world, no per-player or per-region partition.

## Internal evidence that the index is global

The group's own ambiguity rule proves it. "Two doors named 'door' → ask which
one" (LinkedPower Falsifiable checks, `LinkedPower-context-cut.md:84`) can only
arise from a lookup that returns matches from anywhere in the world. A
scope-local index would almost never contain two same-named doors. So "resolve
via entity index" is a global name lookup. That global lookup is exactly what
breaks the create test.

## Concrete counterexample (the common case, not a corner case)

World has been played for a while. A door `door#47` exists in a distant chunk:
manifest, intent record, links to its own lever/latch, motor handle granted to
Alice's builder session (W-7.4, W-9.3). A player standing in a fresh region of
the SAME world, with nothing selected, tasks their personal agent (W-11.2):

    "build a door that opens when a lever is pulled"

Apply the locked gate step by step:

1. Resolve "door" via the global entity index → `door#47` matches. Resolve
   "lever" → also matches (the existing lever). Both roles resolve to ≥1.
2. Therefore `class: modify`, not `create`.
3. Seed = `door#47` and the existing lever. The bidirectional fixpoint walks
   their observed links, joints and handles, includes the alarm if a port is
   modified, applies declared/observed/requested, and emits a 400-token packet
   about a machine three hundred blocks away that the player never selected.
4. The agent acts on that packet — it will rewire or re-plan Alice's door.

This is a wrong-target action, not merely a wrong packet. The
declared/observed/requested distinction does not catch it, because the packet is
internally consistent: it correctly describes the wrong door. BluntDiode's
"preserve disagreements between the task and stored intent as a conflict" only
fires if the task and the bound entity disagree about behaviour; here the task is
generic ("opens when lever pulled") and `door#47`'s intent may say exactly that,
so no conflict surfaces.

Why this is the common case: W-12.1/W-12.2 and W-11.3 mean worlds fill up with
content; after the very first build, ANY subsequent "build a <kind>" task hits an
existing <kind> somewhere in the global index. So the create branch, which the
group just adopted as the dominant workflow (W-5.5, W-11.3), is reachable only in
a world that contains no object of that kind — i.e. almost never.

## What would show me mistaken

If the owner confirms that "resolve via entity index" always means "within the
task's anchor / player selection scope" and that global matches never count, then
zero-match is correctly scoped and there is no bug — the locked text would just
need that one sentence made explicit. But as written the text says "via entity
index" with no scope, and the ambiguity rule requires a global index, so the two
locked statements cannot both be true with a scope-local reading.

## Fix: make binding scope explicit; make the create test reference-scoped

This reuses BluntDiode's binding order (already adopted in principle,
`BluntDiode-task-context-proposal.md:9`) and DirectCobalt's structural-only
determinism (no scoring, no NLP):

Binding order for a named role:
1. explicit entity id in the task (`door#47`);
2. the player's current selection, or the agent's anchor (W-11.2; W-2.2a spawn;
   W-9.1 admin void);
3. global candidates, used ONLY for `modify` disambiguation ("which door?").

Classify on the reference form, not on global existence:

    create  := (main verb in fixed build-verb list) AND
               (role reference is indefinite/bare: "a door", "build a door", OR
                zero matches within anchored scope)
    modify  := definite reference ("the door", "door#47") OR an explicit
               player selection OR ≥1 match within anchored scope

The indefinite article plus a build verb is a deterministic, structural signal
that the player wants a NEW object, independent of whether doors exist elsewhere.
This is the same fixed-verb-list technique the group already locks for the
classifier, extended by one token class (determiner), so it stays O(1) and
server-cheap.

Consequences, all consistent with the lock:
- The brief's example classifies `create` even in a populated world — which is
  the actual requirement.
- "which door?" remains legal only in `modify`, and only when step 3 returns ≥2
  candidates for a DEFINITE/selected reference.
- No invented IDs: in `create` the roles still come from the intent record
  (W-5.5), templates from W-9.4, `requested_links` under *requested* only.
- DirectCobalt's mixed-task rule (R1-24: classify `modify`, report the missing
  role via `unmet_ports[]` as a `create:` element) is unaffected — that is about
  mixed resolution outcomes, this is about which entities are allowed to bind.
- LinkedPower's `user_grants[]` / `blocked_sink` check is unaffected; it operates
  after a seed has legitimately bound.

## Falsifiable checks

- **C4 (populated-world create):** a world containing `door#47` in a distant
  chunk; task "build a door that opens when a lever is pulled" from a fresh
  region, no selection → `class: create`, packet must NOT contain `door#47` or its
  links, must NOT ask "which door?". FAILS if the classifier uses a global index.
- **C5 (definite modify):** same world, "the door won't open when I pull the
  lever" with `door#47` selected → `class: modify`, bound to `door#47`, observed
  links present. FAILS if definite-reference binding is dropped.
- **C6 (conflict surfaced):** "build a door" with `door#47` explicitly selected →
  the selection and the build verb contradict; the packet must report a conflict
  (or an explicit question), never silently pick `create` or `modify`. FAILS if
  the resolver guesses.
- **C7 (regression):** checks 1–8 from the group's table must still pass unchanged
  after the scope rule is added.

## Secondary consequence (same under-specification, stated briefly)

The create path derives role port signatures from the intent prose ("door opens"
→ `in:bool`). The modify path deliberately removed prose-dependence (LinkedPower
R1-14: "goal prose is not an executable predicate"; BluntDiode R1-22: "goal is
prose, not an executable predicate"). So the create fixpoint reintroduces the
authorship-quality dependency the group just eliminated. The mitigation is
already available: prefer the W-9.4 template's declared port signature over the
inferred one, and flag `low_confidence` when no template matches — the same
one-line-widening principle used for a missing `function`. I flag it rather than
argue it separately, because C4/C5/C6 decide the classifier first.

## Net effect on D-W10

The two-class extension is correct but its gate is unusable in a non-empty world,
which is every world after the first build. Adding an explicit binding scope and
a reference-form test makes `create` reachable for the brief's own example
without disturbing any locked selection, rendering, or delivery rule.
