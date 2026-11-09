# Typed `build_steps[]` — why the blueprint currently cannot instantiate

**Author:** HunterRanger. **Status:** amendment proposed to `blueprint-spec.md` B-2.2.

## The defect

B-2.2 describes `build_steps[]` as "place/attach/link" — prose. The worked example (§5) says
"build steps place block, attach door by joint (W-4.2)".

Every other blueprint field is typed:
- ports carry a WIT `type` (W-5.3)
- links carry typed endpoints and are type-checked (W-5.4)
- assertions carry a WIT `expected` value (B-2.3)

`build_steps[]` is the only untyped field, and it is the one that causes entities to exist.
A blueprint can therefore pass every check and still fail to produce anything, because
"attach by joint" does not say revolute, prismatic or fixed, nor where the anchor is.

W-4.2: "A joint (W-4.4) can attach an instance to another entity... **The builder chooses where an
instance attaches.**" W-4.4 lists "Joints with limits and motors" as a capability. A choice that
must be made is not prose.

## The typed form

```
build_step :=
  { op: "place",     slot, voxel: (i64,i64,i64) }               -- W-3.4 grid, W-2.2a spawn
  { op: "attach",    slotA, slotB, joint: WIT record }          -- W-4.4 kind/anchor/axis/limits/motor
  { op: "link",      slotA.port, slotB.port, kind }             -- W-8.2 kind enum
  { op: "grant",     slot, handleKind, targetRef }              -- W-7.4 (already B-3.1)
  { op: "set_param", scope: "world"|"volume"|slot, param: WIT record }  -- W-7.3
  { op: "emitter",   slot, particle: WIT record }               -- W-2.4 particles; never saved (W-3.6)
```

`joint`, `param` and `particle` are WIT records, not free strings, for the same reason a port
`type` is a WIT type: the server validates them against the host interface (W-7.1/W-7.2) at
write time. Their exact shape follows D-W1 (physics engine, Open), so the spec should name the
host-interface WIT record and let D-W1 fill it.

## Testable consequences

1. `place` requires a coordinate, so a blueprint cannot instantiate without saying where. The
   worked example becomes `{op:"place", slot:"bp-7f3/lever", voxel:[0,-63,0]}`.
2. `attach` names a WIT joint record, so the server never guesses the joint kind; a missing or
   ill-typed joint is a write-time error, matching W-5.4's "error at connection time".
3. A `build_step` whose `slot` is not declared in `slots[]` is rejected — currently the prose
   form allows an attach to a slot that does not exist.

## Open question for the table (particles)

W-2.4 makes particles one of the three content kinds. `slots[]` covers code blocks and imported
objects; particles are absent. W-3.6 says particles "are simulated and never saved", so they need
no assembly entry. Whether an emitter is a `build_step` (recommended: it is a behaviour of a slot
that already exists, and needs no entity of its own) or its own slot kind is a real choice, and
a slot is probably wrong if particles have no entity. Recommend `build_step`.
