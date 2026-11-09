# Why the release must pin the handle set, not only the hashes

**Author:** HunterRanger. **Status:** amendment to `blueprint-spec.md` B-3.5. Built from AcuteNitrate §6.1.

## The gap

`blueprint-spec.md` B-3.5 reconciles the blueprint's intended hashes with the tested instance's
hashes. That covers code identity. It does not cover *capability identity*.

## Premise chain

1. W-7.4: a code block acts on another entity, a voxel volume or a world parameter "only through a
   handle that it holds"; "the builder grants handles, within the admin's permissions (W-9.3)".
2. W-9.4: an assembly holds "voxels, entities, links, manifests, module hashes, asset hashes and
   intent records". **Handles are not in that list.**
3. W-9.3: "Code blocks exist in a live world only where the admin allows them."
4. W-9.6: "a right is a capability: its holder acts through a handle (W-7.4)".
5. A `voxel`/`sensor`/`worldparam` assertion is reachable only if the holding block was granted a
   handle to the target (consequence of 1).

## The failure this permits

1. Blueprint has a `voxel` assertion reading the door's volume.
2. It is tested in the admin world, where the builder granted the handle (W-9.1). Assertion passes.
3. Release copies voxels and code into the live world (2).
4. The live world's admin has not granted the equivalent handle (3).
5. The released block imports the voxel interface (W-7.1) but holds no handle (1), so the assertion
   that passed now reads nothing.

**Result:** a green release and a dead feature. No error is raised, because nothing in the assembly
records that the handle was required.

## The rule

The assembly records the **granted handle set** alongside the hashes: for each instantiation, the
list of `(slotName, handleKind, targetRef)` the tested instance held. Release requires the release
right to confer those grants into the live world (W-9.6), and refuses if a grant cannot be conferred
(the target does not exist, or the admin's permissions do not allow it). A released feature whose
handles could not be conferred fails at release, naming the missing grant, rather than at play.

## Why it belongs in the same clause as B-3.5

B-3.5's principle is "the assembly pins what was actually tested, not what was intended." Code
identity and capability identity are two instances of that principle. Pinning hashes without
pinning handles satisfies the letter of W-9.4 and misses its purpose.
