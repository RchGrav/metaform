# `place` needs a cell claim: MS-5 leaves staged voxels unreserved

**Author:** HunterRanger. **Status:** proposed amendment. Raised by ModularShift MS-1/MS-5.

## The forced fix (applied)

`blueprint.submit()` required "every declared slot has at least one `place` step". B-2.2a/M-3 make an **external
role** a slot that is never instantiated and never placed. The two rules are mutually exclusive: every blueprint
with an external role fails submit. Corrected to: every **owned** slot has ≥1 `place`; external roles have none.

## The gap that remains: staged content collides

Trace, with the worked example (B-5):

1. Blueprint A does `{op:"place", slot:"bp-7f3/lever", voxel:[0,-63,0]}` in the admin world (W-9.1).
2. Submission A fails at a later assertion. MS-5: "leaves explicitly inactive only that submission's staged
   content, without undoing unrelated world edits." The block remains at `[0,-63,0]`, inactive.
3. Blueprint B does `{op:"place", slot:"bp-9a1/lever", voxel:[0,-63,0]}`.
4. W-3.4: "A voxel cell holds a material reference or nothing." One cell, one occupant.

Nothing in MS-5 or B-2.2 says B's place is refused or that the cell is reserved. Either B silently overwrites
A's staged block, or the server has an occupancy check with no defined owner. Neither is specified.

## Why it is not hypothetical

W-12.1 requires a faithful Minecraft-like game, where redstone circuits are dense and adjacency is semantic.
Two prototypes built near the origin will target the same cells. Without claims, the second prototype
silently eats the first, and MS-5's "cleanup" cannot tell whose block it is removing.

## Proposed rule

`place` claims a cell. A cell has three states:
- `staged(submissionId)` — placed by a live submission, not active
- `active(instantiationId)` — part of a successful build
- `released` — part of a released assembly

`blueprint.step({op:"place",...})` is refused if the target cell is neither empty nor `staged` by the *same*
`submissionId`. `submit()` success flips this submission's claims to `active`; MS-5 cleanup removes its
`staged` claims rather than "undoing edits", which is what MS-5 already says it does.

## Observable results

- A and B both placing at `[0,-63,0]`: B is refused with `{field:"voxel", reason:"cell staged by sub-A"}`.
- A fails and is cleaned up: the cell returns to empty; B now succeeds.
- A succeeds: the cell is `active(sub-A)`; a later place there is refused.

## Separate note on B-2.3's negative assertion

MS-1: "A rejected type-mismatched link proves a validation rule, not that a valid machine works." My §5 example
uses a refused link as the required negative assertion. That satisfies B-2.3's letter and demonstrates nothing.
Recommend: B-2.3 requires ≥1 **behavioural** negative (a runtime path the machine must not take); structural
negatives are recorded separately and do not satisfy it.
