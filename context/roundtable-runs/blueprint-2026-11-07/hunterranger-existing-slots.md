# Binding a slot to an existing entity: what works and what breaks

**Author:** HunterRanger. **Status:** proposed amendment, needs a table decision. Responds to SeriousMagni's
"the blueprint can create but not modify".

## The gap is real

B-1.3 mints fresh entity ids at instantiation; B-2.2 slots bind to archetypes (content keys). Nothing in the
blueprint targets an entity that already exists. SeriousMagni is right.

## Why the proposed fix ("existing binding reusing the same manifest/type-check machinery") breaks two rules

### 1. It would silently change every instance
W-5.3: "Each code module and each imported asset carries a manifest." W-3.5: "Code modules and imported assets
are stored once, keyed by the hash of their contents."

The manifest belongs to the *content*, not to the entity. An entity is an *instance* of that content. So
"add a `use` port to the existing door" is a request to change the door's archetype, and every other door
instance shares that archetype. The type-check would pass and every door in the world would change.

`blueprint.declare_port` already encodes the correct rule: legal "only on slots this blueprint owns", and a
differing port set "needs a derived content key (recorded as a new module hash, W-9.4)".

### 2. The archetype type-check would use the wrong manifest
`blueprint.link` type-checks "against archetype manifests". For a live entity, the authoritative manifest is the
one on the entity at release time, which can differ from the current archetype's if the module was updated.
Reusing the archetype check would validate a link against a manifest the entity does not have.

## Two operations, not one — and only one needs machinery

| Operation | Requirement | Machinery |
|---|---|---|
| **Attach** a new part to an existing entity (link a new lever to the existing door) | W-5.5 "an agent builds the entity from that intent" | needs an `existing` slot, narrowly |
| **Change** an entity's behaviour (program the NPC) | W-11.2 "possess and program NPCs" | code change = new module hash; rule already exists |

## Proposed rule (narrow)

1. A slot may be `bound: existing(entityId)`. Its manifest is **read from the live entity**, never declared.
2. `declare_port` and `place` are **illegal** on it (it already has a position and a manifest).
3. `attach`, `link`, `grant`, `emitter` are legal.
4. `blueprint.link` for such a slot type-checks against the **live manifest**; for an archetype slot, against
   the archetype manifest.
5. `submit()` rejects an `existing` slot whose `entityId` is absent or outside the admin world (W-9.1).
6. Behaviour change is expressed as a new content key (W-9.4 module hash), not as a port edit on a live entity.

## Observable results

- A blueprint with `bound: existing(entityId)` naming a live door and a `link` to it is **accepted** and wires
  the new lever to the existing door.
- The same blueprint attempting `declare_port` on that slot is **rejected** at write time, naming the verb.
- A blueprint naming a deleted entity is **rejected at submit()** with the missing entity id.
- Every other door instance is **unchanged**, because no archetype was edited.

## Why this was not applied unilaterally

It reverses `declare_port`'s existing constraint (added in an earlier round on W-5.3 grounds). Reversing a shared
decision should be the table's call.
