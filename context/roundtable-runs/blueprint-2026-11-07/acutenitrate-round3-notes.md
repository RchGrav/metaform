# AcuteNitrate — Round 3: two remaining items

The synthesized `blueprint-spec.md` (B-1.1 … D-B6) has absorbed every point I raised in Rounds 1–2, so I am not restating them. Two things remain: one gap in "what a blueprint holds", and a decision the table was explicitly asked to make and left open.

## 1. What a blueprint holds: it is missing a voxel *placement* plan (B-2.5 is over-broad)

B-2.5 says the blueprint "does not hold: … voxel data (W-3.1)". B-2.2 gives each slot only `build_steps[]` (place/attach/link) with no coordinates, materials or link-path geometry. That makes two W-1.4 features unbuildable.

Premises, from `world-system-spec.md`:
- W-8.2: busstone links form by "**Busstone voxels placed between ports**"; the link's "range is the length of the placed path". A busstone link is *made of* placed voxels, not just a graph edge.
- W-12.1 (Decided success criterion): "a faithful Minecraft-like game … redstone from WASM blocks … built on the void as content only". W-8.1 names busstone the prototyping medium. So a blueprint for the flagship content must place voxels.
- W-9.4: an assembly holds "its **voxels**, entities, links, manifests …". Those voxels have to come from somewhere at instantiation.
- W-3.3: *voxel data* is a section's palette + bit-packed indices — the stored chunk content, not a placement instruction.

B-2.5 conflates the two. "Voxel data" (W-3.3 palette/indices, W-2.3 chunk data) must indeed stay out of the blueprint and belongs to the assembly. But an **intended placement** is a different thing: a coordinate, a material reference, and a purpose (e.g. "part of the busstone path for link L"). Without it, `submit()` has nothing to place in the admin world, so W-8.2 busstone links and W-12.1 redstone cannot be instantiated from a blueprint at all.

**Fix:** add `placements[]` to B-2.1 or B-2.2 — `{coord, materialRef, purpose}` — and narrow B-2.5 to "voxel *data* (W-3.3 palette/index records); intended placements are held". A busstone link path is expressed as an ordered subset of `placements[]` sharing a `purpose` tag; a fibre/wireless link (W-8.2) has no placements. Add a `blueprint.place(coord, materialRef, purpose)` verb whose check is that `materialRef` exists in the content key (W-3.5) and the coord is within W-2.2's y = −64…319 range; and make `submit()` reject a busstone-kind link (B-3.1 records link kind) whose `purpose` tag has no placements.

**Observable consequence:** a blueprint declaring a busstone link with no corresponding `placements[]` is rejected at `submit()` with an error naming the link; with placements, the admin world gets a determinate path and W-9.4's assembly has voxels to copy. Under the current B-2.5 the same blueprint is accepted but instantiates nothing.

**What would show this mistaken:** if W-8.2's busstone voxels were supplied by the world server from the link endpoints rather than authored — but W-8.2 says the range *is the length of the placed path*, so the path is authored. Or if `build_steps[]` were already defined to carry coordinates; it is not, B-2.2 only lists "place/attach/link" as names.

## 2. Settle D-B4: the resolver CANNOT be shared with the functional map, so "blueprint-only" is forced, not provisional

HunterRanger (R1-4) left this explicitly open: "whether the resolver model applies to the whole world graph (D-W10) or only to blueprints … I have no argument that settles the first". D-B4 currently recommends "Blueprint-only for now", with no reason. Here is one.

Premises:
- W-5.3's Reason: "`goal`, `function` and `intent` keep the meaning of the functional map's want fields (R-3.6), **so an agent reads both graphs the same way**." This is about *reading* — a shared field vocabulary, which is why W-5.3's reason "hints at" a shared mechanism, as HunterRanger says.
- W-1.1 (Decided): "The functional map is an engineering tool for building the system. It has no role inside a world. **The world system never reads or writes the functional map**, and players never extend it."
- W-5.1: the world graph is "modeled on the metaform technique" — *modeled on*, not *the same instance of*.

Causal step: a resolver that "applies to the whole world graph *and* the functional map" would have to compose layers across both graphs, which requires the world system to read the functional map's layers. W-1.1 forbids exactly that. Therefore a **single shared resolver mechanism is prohibited**; what can be shared is only the *technique* — both graphs independently implement layer composition with the same field shapes (W-5.3's goal/function/intent), and an agent reads both with the same code. That is consistent with W-5.1's "modeled on" and with W-5.3's Reason, and it does not violate W-1.1.

**Recommendation for D-B4:** change "Blueprint-only for now" to "**Blueprint resolver is a separate instance; the functional map's resolver is never called by the world system (W-1.1). Both use the same layer field shapes (W-5.3) so one agent reader serves both.**" This also closes D-W10's recommendation, which currently says "the functional map composes layers … that is one model to compare against" — it is a model to *copy*, not to *call*.

**Observable consequence:** a world-server release contains no code path that resolves a functional-map address; an agent's reader can parse both graphs' `goal`/`function`/`intent` fields with one parser. If someone later proposes a unified resolver, W-1.1 is the cited blocker, so the decision is inspectable rather than a preference.

**What would show this mistaken:** if W-1.1 were only Proposed — it is Decided, with an owner source. Or if "never reads" were scoped to players only; the text says "the world system never reads", i.e. the server itself.
