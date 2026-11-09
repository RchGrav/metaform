# AcuteNitrate — final contribution: a contradiction in `blueprint-spec.md` and its fix

W-1.4 asks two questions: what a feature blueprint holds, and how an agent writes it. `blueprint-spec.md` answers both. I found one remaining internal contradiction in that written answer and corrected it in the file (MS-3, line 111, and the acceptance case, line 130).

## The contradiction

Two clauses in the same document say opposite things about whether an agent declares an "expected manifest contract" for an external role.

- **B-2.2a** (line 34) now reads: an external role "names the target's `worldId`/`entityId` only. Its manifest is **read from the live entity, never declared by the agent** — declaring an expected contract would let the agent's claim drift from the entity's actual manifest, the same failure B-2.3 prevents for selectors, so the type-check would validate against a lie."
- **B-3.1** (line 60) matches: `blueprint.add_external_role(worldId, entityId)` — no `expectedManifest` argument.
- **MS-3** (line 110, before my edit) said: "An external binding records its world/entity id **and expected manifest contract**."

So the spec simultaneously forbids and requires the same field. A reader implementing MS-3 would store an agent-authored contract and type-check against it, while a reader implementing B-2.2a would reject that as validating against a lie. This is a real defect in the answer to "what a blueprint holds": it decides whether the external-role slot carries an agent-declared manifest or not.

## The fix, and why it is not just a wording change

The two clauses are each half-right, and the resolution is to separate *who writes* the value:

- B-2.2a is right that the **agent must not author** the contract: W-5.4's WIT type check would otherwise run against a claim that can disagree with the live entity. That is the same anti-drift principle B-2.3 applies to selectors.
- MS-2 and the acceptance case are right that **some** record of the target's manifest must exist: MS-2 says "Validation records a dependency fingerprint: pinned WIT package definitions, archetype manifests, referenced graph revisions, hashes", and the acceptance case (line 130) requires "Change an external target manifest after validation → Build reports the changed dependency". Without a recorded manifest hash, there is nothing to compare on revalidation.

The value must therefore be **server-recorded, not agent-declared**: at validation the server reads the live entity's manifest and stores its hash in the MS-2 dependency fingerprint. A server-read snapshot cannot drift, because it *is* the entity's manifest at that revision. The agent supplies only `worldId`/`entityId`. This preserves B-2.2a's prohibition, satisfies MS-2's fingerprint, and makes the "change an external target manifest after validation" case meaningful: the stored hash no longer matches the live one, so the build reports the changed dependency.

Concretely, I changed MS-3 to say the external binding "records its world/entity id; the **server** additionally records the target's manifest hash as a dependency fingerprint (MS-2) at validation time. The agent declares **no** expected manifest contract: B-2.2a forbids it… A server-read snapshot cannot drift, since it is the entity's manifest at that revision, and it is what MS-2's dependency recheck compares against." I also changed the acceptance case to name the fingerprint explicitly.

## Observable consequence

Before: a blueprint with an external role has two contradictory implementations — one stores an agent-declared contract and type-checks against it, one refuses to. After: `add_external_role` accepts only `(worldId, entityId)`; the server records the manifest hash; if the target's manifest changes before release, `submit()`/revalidation reports the changed dependency fingerprint (MS-2) and produces no active partial machine (acceptance case, line 130). No agent-authored contract exists to disagree with the entity.

## What would show this mistaken

If W-5.4's type check were meant to run against an agent-declared contract rather than the entity's actual manifest, then B-2.2a is the clause in error and MS-3 was right. But W-5.4 says a link endpoint is "an entity id plus a port name" and the server "refuses a link between ports of different WIT types" — the types are those of the actual endpoints, so the live manifest is authoritative. B-2.2a's reading is the correct one.

## Why this was worth a late-round edit rather than a discussion point

My earlier messages to the table were not delivered, so the W-1.1 argument I offered for D-B4 (resolver scope) never reached the group; D-B4 still reads "Blueprint-only for now" with no reason. Rather than argue a point the table cannot see, I made a change to the deliverable itself, which is visible regardless of message acceptance. The contradiction above is checkable by reading lines 34, 60, 110 and 130 together, and the fix is narrow: it edits two clauses and adds no new field, requirement or open decision.
