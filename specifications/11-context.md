# Context when and where it is needed

This section specifies the addressed-context design, the system's key innovation: the base map stays the intake's exact C(T); everything else is a property held in a knowledge layer, linked at one Address and inherited toward the leaves; and what applies where an agent works is pushed to it there, once, without the agent fetching it. It is governed by `docs/preprint/inference-metaform.md` sections 5.2, 5.3, 6, 7.1, 7.2 and 7.3, and was aligned with the owner on 2026-10-15. The numbered decisions the records cite (decision 1 to decision 25) are those of that alignment.

## Addressing

### CTX-001 The base map is the intake's alone and holds only elements and purpose joins

- Requirement: The base map holds only what the intake records, meaning the elements and the purpose joins in which each RE's OP is served by a PE's EF, and nothing else.
- What this means:
  - The base is the layer of kind `base` that the intake opens and finishes, LAYER-025. It holds elements (address, name_length, name, role) and purpose joins (receiver, held elements, purpose, ef, ifd), MAP-020. Nothing else is written into it.
  - No property, knowledge item, ref, memory link, or element or join an agent adds after the intake goes into the base. All of these go into knowledge layers, CTX-004.
  - The base still changes by refining (`map refine`), which corrects an element or join the intake recorded and keeps every version, LAYER-025. Refining corrects what is there. It does not add a new kind of content.
  - The note field on base elements and joins is removed under the files, refs and names decisions (decision 24), ticket code.graph.knowledge#d.
- Why: The base is C(T) = {(r_i ∧ p_i ∧ e)}, the exact relational identity of the AUE. Paper section 6 separates mutation from transformation, and that needs a core the work does not write into. Everything else is kept in layers that each carry their own question (paper 7.2), so any of it can be selected, hidden, swapped or ported without touching that identity (paper 7.3).
- How it shows: After `intake finish`, a call to `map knowledge` with `add-property`, `add-item`, `add-ref`, `add-element` or `add-join` that names the base leaves the base's rows unchanged. The result's notice names the knowledge layer the record went to. `map refine` on a base join still writes a new version of it in the base.
- Build: To build. Today the finished base accepts these writes. `add_element` (src/metaform/data/writes.py:70-99), `add_join` (:129-151) and `add_property` (:217-247) never call `unchangeable` (:298-307), which stops only in-place edits. LAYER-025's Build lists add-element, add-join, add-property and add-ref as base writes. The write path must check the layer kind (`BASE_KINDS`, src/metaform/data/versions.py:13) and send such a write to a knowledge layer, CTX-011. The intake's own tools (BASE-039) and `refine` (src/metaform/data/layering.py:309) keep writing the base. Tickets: code.graph.knowledge#d for the base note. None of the listed tickets covers sending the other writes to a knowledge layer yet; it belongs beside code.graph.knowledge#b.
- Acceptance:
  - After `intake finish`, add-property, add-item, add-ref, add-element and add-join naming the base each leave every base row unchanged, store the record in a knowledge layer, and return a notice naming that layer.
  - `map refine` on a base join adds a version in the base, and `map history` shows both versions.
  - After any sequence of knowledge writes, the base holds only rows written by the intake tools or by `refine`.
- Relates to: amends LAYER-025 (a finished base no longer takes add-element, add-join, add-property or add-ref; it changes only by refining). Relates to LAYER-001, MAP-001, MAP-020, MAP-040 (the intake produces no properties, unchanged) and BASE-039.
- Status: confirmed, 2026-10-15, in conversation with the owner. Sending such a write to a knowledge layer with a notice, rather than stopping it, is recommended, BASE-044.

### CTX-002 Nothing in the base travels

- Requirement: The base's elements and purpose joins are not transitive. Each is read at its own Address, and only properties (CTX-004) travel the namespace.
- What this means: A purpose join is read as its receiver's join and nowhere else. A base element is not inherited by the Addresses above it toward the leaves. Inheritance, CTX-006, belongs to properties, and the base holds no property.
- Why: A function stays with the one receiver it serves, MAP-022. Spreading a join to every child would give each child a purpose it does not hold, and the base would no longer be the exact C(T).
- How it shows: `map where code.installer.script` lists no join whose receiver is `code.installer`.
- Build: Built. Context reads walk properties only: `context` in src/metaform/data/reads.py:261-290, and `reaching_at` at :293-295, which `where` uses. Joins are read by their receiver. A property written into the base, which a finished base still accepts until CTX-001 is built, does travel today: the applying set adds any current property whose layer reaches the Address (src/metaform/data/reads.py:265-272), with no filter on the layer's kind.
- Acceptance: MAP-022's second acceptance test holds: a join from `code.installer` is received only at that receiver. A base element at `code.engine` is never returned in the applying set at `code.engine.game`.
- Relates to: MAP-022, LAYER-003, LAYER-005, STORE-035. Compare CTX-004, under which joins an agent adds in a knowledge layer do travel.
- Status: confirmed, 2026-10-15; built for the base's elements and joins; holds for properties once CTX-001 keeps them out of the base.

### CTX-003 Genre, style, medium and encoding stay out of the base during intake and are recorded as knowledge after it

- Requirement: The intake keeps genre, style, medium and encoding out of the base. After the intake, they are recorded on the map as knowledge in knowledge layers.
- What this means: The exclusion tells the intake agent what the base holds. It is not a rule about the map as a whole. Once the intake is finished, Addresses such as `code.python`, `platformer.3d`, a style or an encoding are nodes that agents create and link as properties, CTX-004 and CTX-010. The store never judges an Address, MAP-013.
- Why: The base records the functional shape. Genre, style, medium and encoding say how a function is realized or encountered. Paper section 5.2 attaches `code.c` at `code.utility.disk` as an Encounter, here a property in MAP-022's sense, rather than flattening it into `code.utility.disk.c`. This settles the correspondence that paper section 5.3 and docs/inference-metaform/IMPLEMENTATION_MAP.md entry C02 left open: the intake's exclusion and the language-Encounter account are one design applied at two stages.
- How it shows: An intake records no `code.python` element. Afterwards, `map knowledge op=add-element address=code.python` in a knowledge layer is stored, and once it is linked at `code.installer`, `map where code.installer` shows it applying.
- Build: Built. The intake procedure tells the agent to avoid genres, medium, encoding and style (src/metaform/modules/intake/resources/intake.xml:5, and the DE concept at :31). The store accepts any well-formed Address (src/metaform/data/writes.py:78-80, MAP-013). A knowledge layer can create a medium Address (LAYER-016, second acceptance test).
- Acceptance: MAP-013's acceptance test and LAYER-016's second acceptance test.
- Relates to: MAP-013, MAP-017, MAP-020 and LAYER-016. Amends LAYER-028's Why: "a language ... never appears in the metaform's namespace" now means never in the base; it may appear as a knowledge-layer Address.
- Status: confirmed and built, 2026-10-15.

### CTX-004 Everything the intake did not make is a property held in a knowledge layer

- Requirement: Every record the intake did not make is a property held in a knowledge layer. That covers knowledge items, memories, elements and joins that agents add, and refs.
- What this means:
  - "Property" is the general term for anything layered on the base. Each of these is a property: a knowledge item at an element, an element an agent adds (such as `code.python`), a join an agent adds, and a memory's link from a layer. A ref is NOT a property (owner, 2026-10-15): it stays at the one element or join it was linked to, never moves, never inherits and applies nowhere else (CTX-065).
  - Being a property means four things:
    - it is held in a knowledge layer, never in the base (CTX-001);
    - it has one link to one base Address (CTX-008);
    - it is transitive along the namespace (CTX-006, CTX-007);
    - it is selected, hidden, swapped or removed together with its layer (CTX-012, CTX-013).
  - A property recorded at a join (an item, a ref, CTX-065) is linked at the join's receiver Address under the Join rule, and travels from there.
  - Memory content keeps its own shape, the memory graph. What a memory is and how it is written belong to the memory and knowledge decisions (9 to 13). The shape and names of refs belong to the files, refs and names decisions (19 to 25).
- Why: The base is C(T), and everything else is knowledge about it, kept in layers that each carry a distinct question (paper 7.2). With one kind of thing on top of the base, one set of rules decides where it applies, how it is selected and how it is ported. Under the old split, properties travelled and items did not (STORE-035, LAYER-020). That left each memory pinned to a single node and produced the dandelion: 192 memory joins on 21 nodes.
- How it shows: A knowledge item recorded at `code.engine` shows as applying at `code.engine.game`, as a property record does today.
- Build: Partly built. Property records travel (STORE-039, src/metaform/data/reads.py:261-290). Knowledge items are read only at their own node (STORE-035: "Items ... do not travel"). Memories are read only at the node they are joined to (`read_graph node=` in src/metaform/modules/memory/__init__.py). Joins an agent adds are read only at their receiver. To build: the context read returns items, added elements and joins, refs, and memories linked from layers, using the same applying and visible sets as property records. Tickets: code.graph.knowledge#b (inheritance of memories and items) and code.graph.knowledge#c (ref records).
- Acceptance:
  - An item at `code.engine` in a finished, selected knowledge layer is returned as applying at `code.engine.game` and as visible at `code`, and is not returned at `code.installer`.
  - A join an agent adds in a knowledge layer, with receiver `code.engine`, is returned as applying at `code.engine.game`.
  - A ref on `code.engine`'s sources item is returned as applying at `code.engine.game`.
  - A memory linked at `code.engine` is returned by a read at `code.engine.game`; the detail is in the memory records.
- Relates to: amends the following records.
  - MAP-022: in the base an encounter is a function carried by a join; outside the base everything is a property, joins an agent adds included.
  - LAYER-003: "functions are not transitive, so a new element with a function or a purpose reaches the metaform only through its join" now holds for the base only.
  - LAYER-004: "nothing else travels, D73" no longer holds; every property travels.
  - LAYER-016 Build: a knowledge item is no longer either a property or a function, and an element a layer creates is no longer kept from the namespace tree.
  - LAYER-020: "Items do not travel" no longer holds.
  - STORE-035: "Items, and anything attached at joins and subtypes, do not travel" no longer holds.
  - Relates to MAP-021, LAYER-012 and LAYER-013.
- Status: confirmed, 2026-10-15, in conversation with the owner. Built for property records only.

### CTX-005 Every property layer is the same kind, and medium is one example among many

- Requirement: There is one kind of property layer. A property layer is a knowledge layer (CEL, kind `layer`) whose node is a property such as a medium or genre. Medium is one example; genre, style, encoding, storage engine, protocol revision and framework are others, and all of them are handled the same way.
- What this means: Each of these is a node with its own knowledge layer, linked at the base Address where it holds: `code.python`, `code.js`, `code.cpp` (named as the paper's `code.c` is), `platformer.3d`, a style, an encoding, a storage engine, a protocol revision, a framework. The store, the reads, the page and the prompts never treat one kind specially. The list gives examples; it is not a closed set.
- Why: Paper section 5.2 uses a language to illustrate an Encounter, and the same reasoning holds for any Encounter: it applies toward the leaves, is visible toward the trunk, and leaves siblings alone. A mechanism built only for medium would need a second one for every other kind of property.
- How it shows: A genre layer and a medium layer linked at the same element are read, hidden, ported and lit the same way.
- Build: Partly built: knowledge layers are one kind, `layer` (src/metaform/data/layering.py:27), and the store has no record specific to medium; memory is still a separate kind, `memory`. Memories become properties linked from a knowledge layer (CTX-013, CTX-024), ticket code.graph.knowledge#b. The behaviour every kind shares is CTX-006 to CTX-015.
- Acceptance: With `platformer.3d` and `code.python` both linked at one element, the applying, visible, hide and port results are the same for both.
- Relates to: LAYER-002, LAYER-016, LAYER-019 (tags find property layers), LAYER-020 and MAP-013.
- Status: confirmed, 2026-10-15. Partly built: the store has one knowledge layer kind, and memory is still a kind of its own.

### CTX-006 A property applies at its link Address and at every Address above it toward the leaves, on every branch

- Requirement: What is linked at an Address applies at that Address and at every Address above it toward the leaves, on every branch, because children are sub-parts of their parent.
- What this means: Orientation is as in MAP-011: the trunk is down and the leaves are up. A property linked at `code.engine` applies at `code.engine`, `code.engine.game`, `code.engine.game.fps`, `code.engine.physics`, and every other Address with the prefix `code.engine.`. This holds whether the element there is in the base or in a knowledge layer, and for every kind of property in CTX-004. Inheritance follows the namespace tree only, never the purpose joins (LAYER-005 Build). Select, mask and hiding apply as they do for any layer (LAYER-007, LAYER-006).
- Why: Paper 5.2 says that "at the attachment point and its descendants, the Encounter conditions the relevant reasoning." Every prefix of an Address is a complete Type, and a child is a sub-part of its parent (MAP-011), so what holds of a part holds of its sub-parts. One link does the work of a copy at every child.
- How it shows: `map where code.engine.game.fps` lists, as applying, what is linked at `code.engine` and at `code`, each with the Address it is linked at.
- Build: Built for property records. The applying set walks the prefixes of an Address from the trunk up (src/metaform/data/reads.py:261-272), and `where` carries it (:293-295). To build for every other property in CTX-004: ticket code.graph.knowledge#b.
- Acceptance: The acceptance tests of LAYER-005 and MAP-011 pass four times: for a property record, a knowledge item, a join an agent adds, and a memory link.
- Relates to: extends LAYER-005 and MAP-011 from properties attached to elements to everything CTX-004 calls a property. Relates to STORE-035 and MAP-022.
- Status: confirmed, 2026-10-15, in conversation with the owner. Built for property records.

### CTX-007 A property is visible toward the trunk without applying there, and siblings do not inherit it

- Requirement: What is linked at an Address is visible, without applying, at every Address below it toward the trunk. A sibling branch neither inherits it nor shows it.
- What this means: A property linked at `code.engine` is visible at `code` and applies nowhere outside the subtree of `code.engine`. `code.installer` neither inherits it nor shows it. Reads return two separate sets, applying and visible.
- Why: Paper 5.2: "An ancestor can see the Encounter without its sibling branches becoming C." Visibility at the trunk lets a broad question see what is in use across the project (LAYER-022) without spreading one branch's specifics to its siblings.
- How it shows: With Python linked at `code.installer` and C++ linked at `code.engine`, `map where code` shows both as visible and neither as applying. `code.installer` shows Python applying and does not show C++.
- Build: Built for property records (src/metaform/data/reads.py:273-289). For the other properties in CTX-004: ticket code.graph.knowledge#b.
- Acceptance: LAYER-005's first acceptance test and LAYER-022's acceptance test pass, also for knowledge items and memory links.
- Relates to: LAYER-005, LAYER-022, STORE-035 and MAP-011.
- Status: confirmed, 2026-10-15. Built for property records.

### CTX-008 A property has one link to one base Address

- Requirement: Each property has exactly one link, to one base Address. It is never linked twice and never duplicated on a branch.
- What this means:
  - A knowledge item's link is the Address where it is recorded. A property node such as `code.python` (an Encounter type, as the paper's `code.c`; a node held in a knowledge layer, never a layer's name: no layer is named `code` or under it, LAYER-028) has one link, the base Address it is bound at (CTX-014).
  - Recording the same property again does not add a second link; it moves the one link (CTX-009).
  - Because the link is one Address, it covers exactly that Address and the Addresses above it toward the leaves (CTX-006). Moving the link moves everything that comes with it.
  - Open, for the owner: where a property's link goes when its Address, or the common prefix (CTX-009), has no base element, and whether a node's own layer is linked before it is bound (CTX-011, CTX-014); decision 4 says one link to one base Address.
  - Open, for the owner: whether a link may be moved by hand toward the leaves or sideways, by `edit element=` or by binding a layer at a function (CTX-014). Decision 4 says a link never moves toward the leaves; the moves CTX-009 makes by themselves always leave it at a prefix of the old link Address.
- Why: Two links for one property would make it apply twice on a branch, or show one fact in two places. One link that moves gives one place to read, hide or port it.
- How it shows: After a property is recorded at two Addresses, a raw read lists one link for it.
- Build: Partly built. A property record holds one `element_id` (STORE-039, src/metaform/data/writes.py:217-247), and the link can be changed with `edit element=` (src/metaform/data/rows.py:30). Nothing yet stops a second record of the same property at another Address; that is CTX-009's build, ticket code.graph.knowledge#b.
- Acceptance: A property recorded at `code.engine.game` and then at `code.engine.physics` leaves one current record of it, linked at `code.engine`.
- Relates to: settles D88 (how a property is recorded) for its link: one link from the property to one base Address. Relates to MAP-022, STORE-039, STORE-034 (a property's link can be moved) and LAYER-020.
- Status: confirmed, 2026-10-15. Where a link goes when the base has no element there, whether an unbound layer is linked, and whether a link may be moved by hand toward the leaves are open (open questions 20, 21).

### CTX-009 When a property is recorded on another branch, its link moves toward the trunk to where the branches meet

- Requirement: When a property is recorded at an Address its link does not cover, its one link moves toward the trunk to the longest common prefix of the two Addresses, so that it covers both. It never moves toward the leaves.
- What this means:
  - The new link Address is the longest common prefix of the current link Address and the newly recorded Address, compared segment by segment. For example, `code.engine.game` and `code.engine.physics` meet at `code.engine`.
  - If the property is recorded at an Address its link already covers (the link Address or one above it toward the leaves), the link stays where it is.
  - If it is recorded below its link toward the trunk on the same branch, the common prefix is that lower Address, so the link moves there.
  - The link never moves toward the leaves, and the property is never left duplicated on a branch.
  - The common prefix may have no element; one is created there (CTX-010).
  - Agents record where they found something to hold. They are not asked to judge the right depth, because the link settles itself.
- Why: An agent sees one place at a time and cannot know every place a fact holds. Asking it for the most general Address is asking it to judge depth, which this design never asks of an agent (decision 25). Moving the link to where the branches meet is mechanical: one link then covers every place the property was found to hold. Because the link never moves toward the leaves, it never stops covering a place it already covered.
- How it shows: Python is recorded at `code.installer.script` and then at `code.installer.update`. There is one link, at `code.installer`, and `map where code.installer.config` now shows Python applying.
- Build: To build in the knowledge write path (`add_property` and `add_item`, src/metaform/data/writes.py:191-247):
  - Before adding, look for a current record of the same property in the same layer.
  - If one exists, change its link to the common prefix, as `edit element=` does (src/metaform/data/rows.py:30, STORE-034), instead of adding a second record, and say so in a notice.
  - Write the move as a version, so that `map history` shows where the link was.
  - Ticket: code.graph.knowledge#b (the moving link).
- Acceptance:
  - Recorded at `code.engine.game`, then at `code.engine.physics`: one current record, linked at `code.engine`, and it applies at `code.engine.render`.
  - Recorded at `code.engine`, then at `code.engine.game`: the link stays at `code.engine`.
  - Recorded at `code.engine.game`, then at `code.engine`: the link moves to `code.engine`.
  - No sequence of records moves a link to a longer Address.
  - Pending the owner's answer (CTX-008, open question 20): where the common prefix has no element, the case proposed is that an element is created there in the property's layer and the link points to it.
- Relates to: amends STORE-034 and MAP-022 (a property's link can be moved; now it also moves by itself on a second record). Amends LAYER-005 and MAP-011, which say an item that still holds with its leaf segment removed belongs lower: the store now settles the depth rather than the agent. Relates to LAYER-020.
- Status: confirmed, 2026-10-15, in conversation with the owner. Open: where the link goes when the two Addresses share no segment (for example `code.x` and `data.y`). Recommended: an item counts as "the same property" when it has the same value in the same layer; a property layer counts as the same when it is the same node.

### CTX-010 Any Address that does not exist can be created

- Requirement: Any well-formed Address the map does not hold yet can be created, as a node of a knowledge layer.
- What this means: A write that names an Address with no element creates the element there (MAP-016, STORE-026), outside the base (CTX-001). This holds for:
  - knowledge writes: add-element, add-property, add-item and add-join;
  - a link that moves to a common prefix with no element (CTX-009);
  - a memory at a node the map does not hold yet (memory decisions 9 to 13).

  Address form is the only check, MAP-010 and MAP-013.
- Why: Work finds what the intake did not record: a genre, a medium, a function the base lacks. Refusing an Address would make the agent lose what it found, or file it in the wrong place. The store never judges inference, MAP-013.
- How it shows: `map knowledge op=add-element address=platformer.3d` in a knowledge layer stores the element. A memory created at `code.engine.netcode`, which the base lacks, is kept at that Address.
- Build: Built for knowledge writes:
  - `add_element` (src/metaform/data/writes.py:70-99);
  - joins that name an unknown Address (`held_ids`, :116-126, MAP-016);
  - properties sent to a type address (:259-262);
  - items sent to a type address (`node_at`, src/metaform/data/rows.py:286-289).

  Not built for memory: a memory at a node the active map does not hold is refused (LAYER-013, D74). Changing that is the memory records' build.

  Today these make the element in the layer the write names; CTX-011 moves it to the node's own layer.
- Acceptance: add-element, add-property and add-item at an Address the map does not hold each create the element there in a knowledge layer, and the base is unchanged. A memory created at such an Address is stored.
- Relates to: answers LAYER-003's open question 10 and the matching open point in MAP-011's status (an item may attach at an Address no element holds, because the element is created there). Amends LAYER-013: a node the active map does not hold is no longer refused for memory, D74. Amends STORE-020 and BASE-040 (a memory at a node the map does not hold creates the element there). Relates to MAP-010, MAP-013, MAP-016 and CTX-011.
- Status: confirmed, 2026-10-15. Built for elements, joins, properties and items; to build for memory.

### CTX-011 Naming a new node makes a knowledge layer for it

- Requirement: Creating a node the map does not hold makes a new knowledge layer for that node. The layer holds the node, what is known of it, and the links to the memories about it.
- What this means:
  - A new node and its layer come into being together. For example, `platformer.3d`, named for the first time, gets its own layer, which holds the element, the items and properties recorded of it, and the links to memories about it.
  - The layer is a property layer like any other (CTX-005). It has one link to a base Address (CTX-008) once it is bound at a function (CTX-014); whether it is linked before it is bound is open (CTX-008, open question 20). It is selected, masked, hidden and ported as one unit (CTX-012, CTX-013).
  - The layer is named in the layer naming form `<scope>@<content>`, set by the files, refs and names decisions (decision 21).
- Why: A node that stands for a body of knowledge, such as a genre or a medium, has to be selected, hidden and ported as a unit. Giving it its own layer is what makes porting a layer swap (CTX-012) and binding a mashup (CTX-014) with no further machinery, and its memories go with it when it is hidden (paper 7.2, 7.3).
- How it shows: After `add-element address=platformer.3d`, `map layers` lists a new layer for `platformer.3d`. Hiding that layer removes the node, its items and its memories from every context read.
- Build: To build. Today `add_element` writes into the layer the call names (src/metaform/data/writes.py:70-99). A write that names no layer goes to `unnamed-<UTC timestamp>` (src/metaform/data/store.py:138-139) or to the folder's `write_layer` (LAYER-001, BASE-060). Instead, when the Address is new, the knowledge tool's write creates the node's layer, with its provenance record (LAYER-010). None of the listed tickets names this yet; it belongs beside code.graph.knowledge#b. To build: the layer name form (`LAYER_NAME`, src/metaform/data/ids.py:14, and `check_layer_name`, :50-54) admits `@`, so a `<scope>@<content>` name is stored without the not-in-form notice (src/metaform/data/layering.py:114-115).
- Acceptance: Creating a new Address creates exactly one new knowledge layer, which holds the new element. Creating an Address that already exists creates no layer (MAP-016). Hiding the new layer hides the element, the items recorded of it, and the memories linked from it.
- Relates to: amends LAYER-018: a new node's layer is made by the write that names the node, not only by `op=create`. Amends LAYER-001: the `unnamed-` fallback does not apply to a new node. Relates to LAYER-002 (the layer's one variable is what is known of that node), LAYER-028 (naming form, now set by decision 21) and MAP-016.
- Status: confirmed, 2026-10-15. Open: whether a call that names a different layer also writes the node there. Recommended: the node is held only by its own layer, so that hiding the layer hides the node everywhere.

### CTX-012 Porting is a layer swap, and the base never changes

- Requirement: A port replaces one property layer with another. The port reads from the old layer, the new layer is built beside it, and at the end the old layer is hidden or removed. A port never changes the base.
- What this means:
  - Any property can be ported, not only a medium: a language (`code.cpp` to `code.rust`), a genre, a storage engine, a protocol revision, a framework.
  - The base (its elements and purpose joins) is the same before, during and after the port. The function served and who receives it stay the same; only the realization changes.
  - During the port both layers exist. The old one is read, the new one is written, and selection decides what each agent sees (LAYER-007).
  - At the end, the old layer is either hidden, which keeps it (LAYER-006), or removed with `discard` (STORE-032). Hiding it hides everything attached to it (CTX-013).
- Why: Paper section 6 defines mutation as a change of realization that preserves the relational identity, C(T). Sections 6 and 12.2 say a port can use the current realization as one Encounter and the target realization as another. The base is C(T), so it is the invariant the port is checked against. The realization's knowledge lives in layers, so swapping layers is the whole port.
- How it shows: In a port from C++ to Rust, the node `code.rust` is added in its own knowledge layer and linked where `code.cpp` is linked, and is built node by node from what the layer holding `code.cpp` holds. Then the layer holding `code.cpp` is hidden. The base's history shows no version written during the port.
- Build: The mechanics are built:
  - hide and show (src/metaform/data/layering.py:238-245);
  - `discard` for a knowledge layer, which never discards the base (:162-202, the check at :175);
  - select and mask (LAYER-007);
  - layers built from a hidden layer leave context with it (src/metaform/data/selection.py:27-39).

  Running a port is workflow module work (LAYER-020, LAYER-028's port example). CTX-001 is what keeps the base unchanged.
- Acceptance: In a port fixture, the base's elements and joins, with their versions, are identical before and after. After the old layer is hidden, no context read returns its items, links or memories. Showing it again restores them unchanged.
- Relates to: LAYER-006 (its C++ to Rust example is this record), LAYER-028 (the `cpp_to_rust` example), LAYER-020, LAYER-027, MAP-001 and MAP-015.
- Status: confirmed, 2026-10-15. The mechanics of the swap are built. Hiding memories with their layer is CTX-013.

### CTX-013 Hiding a layer hides everything attached to it, its memories included

- Requirement: Hiding a layer removes from every view and every agent context everything attached to it: its elements, joins, items, refs, and the memories linked from it.
- What this means: Memories are kept in the memory graph and linked from the layer they belong to (memory decisions 9 to 11). While that layer is hidden, those memories show nowhere and are not pushed to agents (pushed-delivery decisions 14 to 18). They are kept, and they reappear when the layer is shown. This is separate from turning off the `memory` layer itself, which LAYER-012 covers.
- Why: A hidden layer's knowledge must stop steering agents (LAYER-006). Memories about C++ ownership, pushed to an agent writing Rust, would steer it wrong. A port ends with the old property hidden (CTX-012), and its memories are part of what is hidden.
- How it shows: After the layer holding `code.cpp` is hidden, neither `memory read_graph node=element:code.engine` nor `map where code.engine contents=true` returns any memory linked from it. `map unhide` brings them back.
- Build: To build. Today a memory shows wherever the one `memory` layer reaches the Address (src/metaform/modules/memory/__init__.py:219-225), and that check does not know which layer the memory is linked from. The memory read must also check the linking layer against the effective selection and the hidden closure (src/metaform/data/selection.py:27-39). Ticket: code.graph.knowledge#b.
- Acceptance: A memory linked from layer L at `code.engine` shows at `code.engine.game` while L is shown. While L is hidden it is absent from every read, the whole-graph read included. It returns unchanged when L is shown again. A memory not linked from L is unaffected throughout.
- Relates to: amends LAYER-006 (hiding now also covers the memories linked from the layer) and LAYER-012 (a memory at a node shows only where both the memory layer and the layer it is linked from reach). Relates to LAYER-013 and VIEW-031.
- Status: confirmed, 2026-10-15.

### CTX-014 A property layer bound at a function is inherited by everything under that function

- Requirement: A property layer can be bound at the Address of a function, and everything under that function then inherits it.
- What this means:
  - Binding means setting the property layer's one link (CTX-008) at the Address of a function in the base.
  - Example: `platformer.3d`, a genre taken from SM64, is bound at the Address of a host game's open-world traversal function. Every sub-part of that traversal then inherits `platformer.3d` and what its layer holds. This is how a game mashup works, for example SM64's platforming in Spider-Man 2's traversal.
  - The Addresses are whatever the host's intake produced; the mechanism does not name them.
  - Sibling functions, such as combat, do not inherit the layer (CTX-007).
- Why: Paper 5.2: an Encounter attached at a function conditions the reasoning at that function and its descendants. A genre is knowledge about how a function is encountered. Binding it at the function carries one project's realization into another's functional shape without changing that shape, which is the base (CTX-001).
- How it shows: With `platformer.3d` bound at the traversal function's Address T, `map where` at any Address under T lists `platformer.3d` and its knowledge as applying. At an Address outside T it does not.
- Build: Built for property records. A property attached to an element applies toward the leaves (src/metaform/data/reads.py:261-272); that is LAYER-020's case of C++23 linked at the main loop. To build: binding the layer as a whole, so that its items and memories come with it (CTX-004, CTX-011). Ticket: code.graph.knowledge#b.
- Acceptance: A `platformer.3d` layer holding two items is bound at Address T. Both items apply at every Address under T and at none outside it. Hiding the layer removes both.
- Relates to: LAYER-005, LAYER-020 (a property decides where a layer's tasks are created; its platformer-layer example), LAYER-027 (a workflow's layer is turned on where it applies) and MAP-022.
- Status: confirmed, 2026-10-15.

### CTX-015 Clicking an item or the node it is linked at makes the path where it applies glow, on both maps

- Requirement: Clicking an item, or the node it is linked at, makes the whole path where it applies glow on both the 3D and the 2D map, by lighting what is already drawn. Inheritance is never drawn as lines.
- What this means:
  - What is lit is the link Address and every Address above it toward the leaves, on every branch: the applying set of CTX-006. The Addresses below it toward the trunk, where the item is only visible, are not lit.
  - Every kind of property starts it: a knowledge item, a property, a memory, a ref, or an element or join an agent added. Clicking a node lights the path for what is linked at that node.
  - The glow is light given off by the nodes and namespace edges already drawn (VIEW-029, VIEW-025). No line, arrow or connector is added to show inheritance.
  - Selecting anything else puts the map back.
- Why: Where something applies cannot be seen until someone asks. Lighting the map already drawn answers that in place, without adding lines that would bury the map. Addresses toward the trunk are not lit because nothing there inherits the item.
- How it shows: Clicking a memory linked at `code.timer.kitchen` lights `code.timer.kitchen` and every element above it toward the leaves, in both views, and leaves `code.timer` and `code` unlit.
- Build: Partly built.
  - `setReach` (src/metaform/modules/web/page/app/map3d/waves.js:29-47) lights a reach in 3D and toggles a `reach` class on the 2D boxes. It only starts from property records (keys beginning `r:`, at :30, made in src/metaform/modules/web/page/app/loading/load.js:64).
  - `elementsAlong` (waves.js:48-54) includes every Address toward the trunk.
  - To build: start the glow from every kind of property and from a node, and limit the lit set to the applying side.
  - Ticket: code.graph.knowledge#b (click to glow).
- Acceptance:
  - VIEW-022's test, amended: selecting a property linked at `code.timer.kitchen` lights `code.timer.kitchen` and every element toward the leaves from it, and does not light `code.timer`.
  - The same holds for an item and for a memory at that node, and clicking the node lights the same set.
  - While the path is lit, no line or connector between nodes is added to either view.
- Relates to: amends VIEW-022, whose reach included the Addresses toward the trunk and started only from a property node; now any property or its node starts it, and only the applying side is lit. Amends VIEW-026, whose wave sends dots toward the trunk as well and draws a mesh for each dot; under this record the path is shown by lighting the nodes and edges already drawn. Relates to VIEW-029 and VIEW-031.
- Status: confirmed, 2026-10-15, in conversation with the owner. Open: whether VIEW-026's wave remains as a pulse running only toward the leaves through the lit nodes, and whether VIEW-022's particles along the lit edges stay.

## Memory

### CTX-020 A memory is what an agent writes because it will help other agents, kept in the memory graph at an Address

- Requirement: Memory is the standard MCP memory server, with an Address on the map to hang each memory at. An agent writes a memory because it will help other agents working there. Memory has no tie to tickets and holds no history of tickets or work: a ticket's disposition is recorded on the ticket.
- What this means:
  - Agents keep memory as the standard server's prompt keeps its graph: create what helps, update what changed, delete what no longer helps. Nothing in a ticket's flow writes or requires a memory.
  - The graph is the MCP reference memory server's, as LAYER-013 gives it. Entities have `name`, `entityType` and `observations`. Relations have `from`, `to` and a `relationType` written in active voice. Each observation holds one fact. The tools are memory's: `create_entities`, `create_relations`, `add_observations`, `delete_entities`, `delete_observations`, `delete_relations`, `read_graph`, `search_nodes` and `open_nodes`.
  - A memory is recorded at the Address it concerns. Under the Join rule that is the RE whose goal the work served, as memory's rule already says (`src/metaform/modules/memory/resources/prompts.xml:26`).
  - Whether a finding is memory or knowledge is the agent's call. Metaform never checks or sorts it (decision 25).
- Why: Paper 7.1: memory has a functional location. The 2026-10-15 investigation found 193 memories made under prompts that said only "store what you learn under <node>". Those memories mixed what happened with what is true. They sat on 192 joins at 21 nodes, and their 9 relations all stayed inside one node: the dandelion. Knowledge kept in memory cannot be inherited, selected, hidden or ported with the layer it belongs to. Memory is cheap and mutable with no history (STORE-018), and that fits a record of events. It does not fit facts that other parts of the map inherit.
- How it shows: An agent that fixed a defect at `code.store.memory` calls `create_entities` with an entity of type `fix`. Each observation holds one fact, and `node=element:code.store.memory`. A later `read_graph node=element:code.store.memory` returns it.
- Build: The graph and its nine operations are built: `src/metaform/modules/memory/__init__.py:608-853`, on the tables of STORE-020. The definition reaches agents through the memory prompt, CTX-026. Recommended: a memory layer made from now on states its variable as "What happened in the work at this node." The existing layer's variable reads "What agents have noted at this node.", LAYER-012, and is left as recorded. Ticket: the memory prompt package (CTX-026).
- Acceptance: `create_entities` at a node followed by `read_graph` there returns the entity with its observations in order (existing, `src/metaform/modules/memory/tests/test_memory.py`). The definition reaches agents as CTX-026's acceptance checks.
- Relates to: LAYER-012 (amends: the variable of a memory layer made from now on, recommended), LAYER-013, STORE-018, STORE-020, BASE-040, CTX-021, CTX-026.
- Status: confirmed, 2026-10-15, in conversation with the owner. The graph and its operations are confirmed and built.
- Amendment, 2026-10-19, the owner in conversation with the system agent: memory is the standard memory server with an Address to hang memories at; the earlier wording, memory as "the history of the work", led agents to write work logs, and is replaced. The forced record-on-finish turn is removed by ticket code.dispatcher.agent#80.

- Amendment, 2026-10-21, code.store.memory#2e: retrieval starts with `search_nodes` using the task's own words at its assigned functional node, followed by `open_nodes` for relevant matches. `read_graph` remains an explicit whole-graph read. The shared prompt retains durable, atomic knowledge maintenance and directed relations. `read_unread` and agent node context list `name`, `entityType`, `title` and one-line `why`, with titles and reasons limited to 160 characters each, without observations or relation bodies. Discovery leaves body receipts unread. Applicable withdrawal records remain available. The new-memory arrival count stays. The ticket panel lists titles and fetches one selected memory when opened, replacing its whole-graph Mermaid chart.
- Acceptance for this amendment: a 55-entity, 232-observation fixture measures canonical-body versus title-only context bytes, confirms discovery leaves bodies unread, and verifies selective search/open bodies. Scoped reads resolve visibility and address joins before materializing observations, citations and incident relations. Masked selections materialize no bodies. Explicit graph reads preserve all visible entities and cross-address relations. Ticket-panel checks prove no initial body fetch and one selected body on expansion.

### CTX-021 Knowledge is what is true of the project, and it is written to knowledge layers, never to memory

- Requirement: Knowledge, meaning what is true of the project, is written to knowledge layers with the map's knowledge tool and corrected with `map refine`. It is never kept in memory.
- What this means:
  - Knowledge covers:
    - what an element is and the files that realize it
    - how it behaves and fails
    - the constraints and choices that hold for it
    - the purpose it serves
    - the elements it receives from and provides to
    - its genre, style, medium and encoding
  - The intake keeps genre, style, medium and encoding out of the base. After the intake they belong on the map as knowledge (decision 1).
  - Writes:
    - `map knowledge op=add-element` and `op=add-join` add what the map lacks.
    - `op=add-property` and `op=add-item` record what is known at an Address.
    - `map refine` corrects an element or join that is wrong.
  - Which layer and which Address a piece of knowledge lands in, and how it is inherited and moved, belong to the addressing records (decisions 2 to 5, CTX-004 to CTX-011). Knowledge is a property held in a layer (decision 2), so it inherits, hides and ports with its layer.
  - Drawing the line between memory and knowledge is the agent's call (decision 25).
- Why: Paper 7.2: layers keep distinct questions and perspectives apart, and a layer is what gets selected for an operation. Knowledge kept in the memory graph was reachable only at the exact node it was joined to. No select, mask, inheritance or port could reach it.
- How it shows: An agent that finds `code.store.memory` is written in Python records Python as a property at `code.store.memory` with `map knowledge op=add-property`. It does not create a memory saying so.
- Build: The tool and refine are built: `src/metaform/modules/map/__init__.py:698-712` (operation fields), `:914` (`add-property`), `:963` (the `op` noun) and `:819` (`refine`). Placement belongs to the addressing records. The definition reaches agents through the memory prompt, CTX-026.
- Acceptance: As CTX-026's and CTX-030's acceptance: after the reprocess, every observation that was knowledge is found as an item or property in a knowledge layer.
- Relates to: LAYER-005, LAYER-016, LAYER-018, LAYER-025, MAP-022, CTX-020, CTX-026.
- Status: confirmed, 2026-10-15, in conversation with the owner. The knowledge tool and `map refine` are confirmed and built.

### CTX-022 Any agent may create, read, update or delete any memory

- Requirement: Any agent may create, read, update or delete any memory at any time, including memories other agents wrote, unless the memory is locked, CTX-023.
- What this means:
  - No memory belongs to the agent that wrote it. The `by`, `session` and `at` on joins and observations (STORE-020) record who wrote what and when. They never restrict who may change it.
  - Updating works the reference's way:
    - `add_observations` adds an observation.
    - `delete_observations` removes one. Replacing an observation means adding the new one and then deleting the old.
    - Relations are made and deleted with their own operations.
    - The person can also rename or retype a memory from the page, VIEW-031.
  - At a node, reads return the applying set (CTX-024); writes (`add_observations`, the deletes) name an entity anywhere in the graph, and only a name the graph lacks stops the call. Without a node they act on the whole graph.
- Why: Memories exist to share what happened, and a wrong one misleads every agent that reads it. Whoever finds it wrong fixes it where they stand (LAYER-012). An ownership check would leave a wrong memory standing until its writer came back, and a finished session never comes back.
- How it shows: A session with `METAFORM_SESSION=r2` deletes an observation that session `r1` wrote, and later deletes the whole entity. Both calls succeed, and `memory graph` no longer shows them.
- Build: Built. No write checks `by` or the session: `add_observations`, `delete_entities`, `delete_observations` and `delete_relations` in `src/metaform/modules/memory/__init__.py:714-793`.
- Acceptance: A memory written under `METAFORM_SESSION=r1` is given a new observation, has an observation deleted, and is then deleted, all under `METAFORM_SESSION=r2`. Each call succeeds and the graph shows each change.
- Relates to: LAYER-012 (amends "any agent may read them and add to them": any agent may also change and delete them, unless locked), LAYER-013, STORE-018, STORE-020, BASE-040, VIEW-031, CTX-023.
- Status: confirmed and built, 2026-10-15, in conversation with the owner. Locking is the exception and is not built, CTX-023.
- Amendment, 2026-10-17, UX review round 1, fix group person-consent (memory deletes had no caution): `delete_entities`, `delete_observations` and `delete_relations` are the person's decision (`person_says`): no copy is kept, so each runs only with the person's `--confirm` on their command line, their yes to their AI tool's form, or from the page's memory panel. An agent may still create, read and add to any memory; its delete is refused with the caution, naming what would go, and the command the person runs. This narrows the record's 'delete any memory' for agents.
- Amendment, 2026-10-19, ticket code.store.memory#c, updating the record to the code: the 2026-10-17 amendment no longer holds. The GC-led orchestration change (commit 4f2966c8, merged 2026-10-18 in 9eb0eed5) took the caution and `person_says` off the three deletes and gave agents a memory prompt that has them remove outdated entities, observations and relations and refine an observation by deleting it and adding its replacement. An agent's delete runs like its other writes, as this record's requirement says; the lock (CTX-023) is what keeps a memory the person has confirmed. The tools stay marked destructive (`effect='remove'`).

### CTX-023 Every agent can read a locked memory, and no agent can change or delete it

- Requirement: A memory can be locked. While it is locked, no agent can change or delete it, and every agent still reads it.
- What this means:
  - A lock covers the entity, its observations, its title and why, its citations and its memory joins. A call that would write or delete any of these for a locked memory leaves it unchanged:
    - `add_observations`
    - `delete_observations`
    - `delete_entities`
    - `create_entities` with its name
    - `unjoin`
    - `rekey`
  - Relations are records of their own. Recommended: another memory may be related to a locked one in either direction, but a relation that touches a locked memory cannot be deleted.
  - A call that names several memories writes the unlocked ones and lists the locked ones in its result, in the form the reference already uses for a partial delete: `Deleted 0 of 1 entities. Locked: <name>`. A lock is mechanics, not a judgement of content, so it is one of the refusals decision 25 allows. It is not a refusal of content under BASE-044.
  - Recommended: only the person locks and unlocks, from the page's memory panel and from the command line. `lock` and `unlock` are never MCP tools, just as `approve` is CLI-only (LAYER-015) and the note is the person's alone (VIEW-034).
  - Reads show the lock: `open_nodes`, `read_graph` and `search_nodes` return a locked memory unchanged. The memory read `metaform://<address>#<n>`, `graph` and pushed content mark it `locked`, so an agent learns about the lock before it tries a write.
- Why: Decision 11. Open CRUD lets agents fix each other's memories, and it also lets them wear away one the person has confirmed. The lock keeps open CRUD safe without restoring ownership.
- How it shows: The person locks `route ejection` in the page's memory panel. An agent's `memory_delete_entities ["route ejection"]` returns `Deleted 0 of 1 entities. Locked: route ejection`, and `memory_open_nodes ["route ejection"]` returns the memory unchanged. After `metaform memory unlock "route ejection"` the same delete succeeds.
- Build: To build. There is no lock in `src/metaform/modules/memory/__init__.py` today. Recommended:
  - Memory tables version 7 adds `locked_by` and `locked_at` to `entities`, empty when unlocked. `compatible_from` rises to 7, because older code would write past a lock it does not know about (STORE-029). Version 6, the citations table, is already built (`TABLES_VERSION = 6`, src/metaform/modules/memory/__init__.py:65).
  - Verbs `lock` and `unlock` are declared for the `cli` and `web` surfaces.
  - Every writing command checks, inside its transaction, the entities it touches.
  - The memory panel (VIEW-031) gets Lock and Unlock.
  - None of the 2026-10-15 tickets builds this. A ticket is to be raised at `code.store.memory`.
- Acceptance:
  - On a locked memory, over MCP and on the command line, `add_observations`, `delete_observations`, `delete_entities`, `unjoin` and `create_entities` of its name change nothing, and each names the lock.
  - `read_graph` and `open_nodes` return the memory unchanged.
  - `lock` is not in the MCP tool list.
  - After `unlock` the same calls succeed.
  - A store at version 6 opens at version 7 with every memory unlocked.
- Relates to: CTX-022, LAYER-012, LAYER-013, LAYER-015, STORE-020 (amends: the lock columns, tables version 7), STORE-029, BASE-040 (amends: the `lock` and `unlock` verbs), BASE-044, VIEW-031 (amends: Lock and Unlock in the memory panel), VIEW-034.
- Status: confirmed, 2026-10-15, in conversation with the owner: a locked memory is exempt from agents' CRUD. Who locks, what a lock covers, how relations to a locked memory behave, and the storage are recommended.

### CTX-024 A memory applies at the Address it is linked at and at every Address above it toward the leaves

- Requirement: A memory linked at an Address applies there and at every Address above it toward the leaves, on every branch. It is visible, without applying, at every Address below it toward the trunk. Siblings do not inherit it.
- What this means:
  - Memories follow the same rule as every property (decision 3; LAYER-005; MAP-011). Children are sub-parts of their parent, so what happened at `code.store` concerns `code.store.memory` too. A memory at `code.store.memory` says nothing about `code.store`'s other children.
  - A memory is transitive with the layer it is linked from. A node's own layer links the memories about that node (decision 5). A property's layer, such as a medium's, links the memories about that property. Hiding the layer hides its memories (decision 6). A memory has one link (CTX-008). When it is joined at an Address on another branch, its link moves toward the trunk to the common prefix (CTX-009). When a property's link moves toward the trunk (decision 4), the memories that layer links apply wherever the link now is.
  - At a node, "the memories here" becomes the applying set: those linked at the node, plus those inherited from each prefix toward the trunk, each marked with the Address it is linked at. Recommended: the visible set (memories linked toward the leaves from the node) is counted and listed on request, never delivered whole.
  - Every read that takes a node acts on the applying set; writes at a node name an entity anywhere in the graph, and only a name the graph lacks stops the call (CTX-022, as CTX-025 does for relation ends):
    - `read_graph`, `search_nodes` and `open_nodes`
    - `map where` and `map node` (memory's `node_read`)
    - the counts (MCP-039) and `items_at`
    - `this.memories` (MAP-057)
    - pushed delivery (decisions 14 to 18)
  - Inheritance follows the namespace tree only, never purpose joins (LAYER-005's Build), so it always terminates. A memory on a join is linked at that join's receiver (the Join rule), and it is inherited from there as any memory is. An element read already shows the memories on the joins it receives and provides.
- Why: Paper 5.2: forward application toward the leaves, backward visibility toward the trunk, and siblings untouched. Paper 7.1: memory has a functional location. Today a memory is seen only at the exact node it is joined to: `_view` (`src/metaform/modules/memory/__init__.py:341`), `node_read` (`:1002-1035`) and `node_count` (`:1036`, an exact `receiver` match). So an agent at a child never saw what happened at its parent, and agents pinned one memory to each leaf. One link, inherited, replaces a join at every node.
- How it shows: A memory is joined at `code.store`.
  - `map where code.store.memory` lists it under `memory`, marked as inherited from `code.store`.
  - `memory_read_graph node=code.store.memory` returns it.
  - `memory_add_observations` to it with `node=code.store.memory` succeeds.
  - At `code.graph`, a sibling branch, it is absent from reads; `add_observations` to it with `node=code.graph` finds it in the whole graph and succeeds, and only a name the graph lacks stops with `Entity with name <name> not found`.
  - `map where code` counts it as visible from above and does not deliver it.
- Build: To build, ticket `code.graph.knowledge#b`. Recommended mechanism:
  - The applying set at Address A is read trunk first, as MAP-011's Build walks the prefixes: for each prefix of A, the memory joins with that prefix as `receiver` and an empty `provider`, one keyed read per prefix on the `receiver, provider` index (STORE-020). To these are added the memories linked from the layers that apply at A (the addressing records).
  - Each prefix is filtered by whether memory reaches it (`_reaches`, `src/metaform/modules/memory/__init__.py:219-225`), so a mask or a hidden layer still removes what it covers.
  - The visible set is one range read on `receiver`, from `A.` up to but not including `A/`, as STORE-019 resolves a subtree.
  - A memory with joins at several nodes is reduced to one link at their longest common prefix, as part of the reprocess (CTX-030).
- Acceptance:
  - The case under How it shows: inherited at the child, absent at the sibling, visible only at the parent.
  - Masking memory at `code.store.memory` removes the inherited memory there while it still shows at `code.store`.
  - Hiding the layer a memory is linked from removes it from every read and push at every Address.
  - A burst of memory writes at Addresses outside a node's prefixes causes no read for that node's push (CLAUDE.md section 2, rule 5).
- Relates to: LAYER-004 and D73 (amends "nothing else travels": memories travel as properties do), LAYER-005, LAYER-007, LAYER-012, LAYER-013 (amends "given a node, each acts on that node's memories … the entities joined to the node": its reads return the memories that apply at the node, and its writes name an entity anywhere in the graph; the acceptance case "`add_observations` to an entity joined to another node stops" becomes "`add_observations` at a node stops only for a name the graph lacks"), MAP-011, MAP-057 (amends `this.memories`: the applying set, each with the Address it is linked at), MCP-039 (amends: memory counts count the applying set, inherited ones marked), BASE-040 (amends `node_read`), STORE-019, STORE-020, VIEW-031, CTX-008, CTX-009, CTX-022, CTX-025, CTX-030.
- Status: confirmed, 2026-10-15, in conversation with the owner. The read mechanism and counting the visible set without delivering it are recommended.

### CTX-025 Memories are related to each other across Addresses

- Requirement: A memory can be related to any other memory, wherever each is linked, and every relation shows from both of its ends.
- What this means:
  - Relations connect what happened at one part with what happened at another. For example, a fix at `code.store.memory` `repairs` a defect found at `code.interface.graphical`. These are the edges the memory prompt's step 5b asks for.
  - `create_relations` at a node takes ends from anywhere in the graph. An end that does not apply at the node is looked up in the whole graph. Only a name the whole graph lacks stops the call, with the reference's `Entity with name <name> not found`, before anything is written.
  - A read at a node returns the memories that apply there, CTX-024, and every relation with at least one end among them. The reference's `open_nodes` and `search_nodes` already return relations this way (LAYER-013). The far end is cited as `<address>#<n>  <title>`, so the agent can open it.
  - `create_entities`, `add_observations` and `create_relations` without a node currently add a notice saying that no node will show a relation whose ends share no node, and telling the agent to pass `node` (`_unshown`, `src/metaform/modules/memory/__init__.py:579-587`, called in `create_relations` at `:703-706`). That notice is dropped, because such a relation now shows at both ends.
- Why: Decision 11. In the 2026-10-15 investigation, all 9 relations sat inside one node. A relation across nodes was refused when the call named a node, and warned against when it did not. Memories related only within one node make a dandelion, not a graph. Following relations is how the prompt's step 3 ("search_nodes and open_nodes for what that leads to") reaches the history that bears on the work.
- How it shows: `memory_create_relations [{"from":"dock fix","to":"route ejection","relationType":"repairs"}] node=code.interface.graphical`, with `route ejection` linked at `code.manager.route`, makes the relation. `read_graph` at either node returns it, with the far end cited by number and title.
- Build: To build with `code.graph.knowledge#b`. The reprocess, `code.store.memory#2`, depends on it.
  - Already built: the memory read lists relations in both directions with citations (`src/metaform/modules/memory/__init__.py:1105-1108`), and the whole-graph reads without a node (`:811-853`).
  - To change: the end check in `create_relations` (`:691-696`), the relation narrowing in `_view` (`:341`), `node_read` (`:1002-1035`), and the unscoped notice (`_unshown`, `:579-587`, called at `:703-706`).
- Acceptance:
  - The relation under How it shows is made and read from both nodes.
  - A `create_relations` naming a name that is not in the graph writes nothing and names it.
  - Without a node, a cross-address relation is made with no notice.
- Relates to: LAYER-013 (amends "the relations between them": at a node, every relation with at least one end among the memories that apply there; and `create_relations` at a node looks up an end in the whole graph), BASE-040 (amends: the unscoped notice for relations is dropped), VIEW-031 (unchanged: the memory network already draws the memories that relations name), CTX-024, CTX-030.
- Status: confirmed, 2026-10-15, in conversation with the owner. The lookup rule and the read shape are recommended.

### CTX-026 Every agent works by the owner's memory prompt, sent word for word

- Requirement: Every agent receives the owner's memory prompt, word for word, and works by it.
- What this means:
  - The prompt, exactly as the owner wrote it. Its fills are CTX-027, and when it is sent is CTX-028:

    ```
    Follow these steps for each interaction:
    1. Project Identification:
       - You should assume that you are working on {project}
    2. Element Identification:
       - This is {this.address} ({this.name}) or any other address you work on for this session.
    3. Memory Retrieval:
       - Always begin your work by saying only "Remembering..." and retrieve all relevant information from your knowledge graph: everything at the element's address and everything it inherits from the addresses below it toward the trunk, then search_nodes and open_nodes for what that leads to
       - Always refer to your knowledge graph as your "memory"
    4. Memory and Knowledge
       - While working on the project, be attentive to any new information, and tell which it is:
         a) Memory: what happened in the work: what was done, tried, decided, found broken or fixed, and the lessons it taught
         b) Knowledge: what is now known to be true of the project: what an element is and the files that realize it, how it behaves and fails, the constraints and choices that hold for it, the purpose it serves, the elements it receives from and provides to, and its genre, style, medium and encoding, which the base map leaves out
    5. Memory Update:
       - If any memory was gathered during the work, update your memory as follows:
         a) Create entities with create_entities for significant events, decisions, defects and lessons: each with a unique name, an entityType and its observations, at the address it concerns
         b) Connect them to the current entities using create_relations: from, to, and a relationType in active voice
         c) Store facts about them as observations with add_observations, one fact per observation
    6. Knowledge Update:
       - If any knowledge was gathered during the work, add it to the map's knowledge layers as follows:
         a) Any address that does not exist yet can be created: add the element or join the work shows the map lacks with map knowledge add-element and add-join; naming a new element makes a new layer for it
         b) Record what is known at the address where you found it to hold, with map knowledge add-property or add-item, including its genre, style, medium and encoding
         c) Correct any element or join that is wrong with map refine
    ```

  - Recommended: it is stored as memory's `<instructions>` element in `src/metaform/modules/memory/resources/prompts.xml`, with the Address `prompt.memory:instructions` (decision 23). It replaces the Axiom text that element holds today, which CTX-029 supersedes. It is served through the prompt store (STORE-044), so a person's override is what agents receive, and the Axiom text stays readable as an earlier version.
  - It is sent whole and is never cut. At 2,238 bytes it is larger than `node_summary_bytes`, but it is not node content, so that budget does not apply to it.
  - The prompt names commands as the owner wrote them (`map knowledge add-element`, `map refine`). Over MCP these are the `map_knowledge` and `map_refine` tools. The text is not rewritten per surface.
  - `create_entities` refuses a new memory that has no why and names what is missing (BASE-040). That refusal teaches the title and why, so the prompt does not need to. It is one of the mechanics CTX-091 lists.
- Why: Decision 12. The dandelion came from prompts that said only "store what you learn". This prompt separates memory from knowledge, says where each goes, and makes reading what applies come first.
- How it shows: `metaform_instructions module=memory` and `metaform://instructions/memory` return the prompt with its places filled. A dispatched worker's first turn carries it, and the worker begins by saying "Remembering...".
- Build: To build. Ticket: the memory prompt package that `code.store.memory#2` and `code.graph.knowledge#b` are held on. No ticket in the 2026-10-15 list builds the prompt element itself, so one is to be raised at `code.store.memory`. The comment above the element states what it is, who receives it and when, and how to override or turn it off (MCP-031).
- Acceptance:
  - A test reads the stored element and compares it byte for byte with the text above, with its places unfilled.
  - An override saved through the prompt store is what a dispatched worker receives.
  - The earlier Axiom text is still readable as the element's previous version.
- Relates to: MCP-031, MCP-035, STORE-044, BASE-040, CTX-020, CTX-021, CTX-027, CTX-028, CTX-029, decision 23 (prompt addresses).
- Status: confirmed, 2026-10-15, in conversation with the owner. The wording is the owner's. Storing it as memory's `instructions` element is recommended.
- Amendment, 2026-10-16, the owner's orchestrating session, no ticket: the text above was a Claude draft, not the owner's approved wording; the owner's recovery of 2026-10-15 shows no final version was approved. The shipped `instructions` element is now the owner's recovered prompt (section A of that recovery), with what the owner added on 2026-10-16: 6a creates an address only as the intake's namespace rules allow, given word for word from `intake/resources/intake.xml`, with their bars on genre, style, medium, encoding and language holding for the base map only; 5f, a memory sits at the element or at the join it concerns; 5g, it cites its evidence. `{element}` is the assigned element's address, filled by the memory module; `{this}` keeps its designed meaning, the subject a prompt or workflow is linked to, and the memory prompt no longer fills it. This block supersedes the one above:

    ```
    Follow these steps for each interaction:

    1. Project Identification:
       - You should assume that you are working on {project}

    2. Element Identification:
       - This is {element} or any other address you work on for this session.

    3. Memory Retrieval:
       - Always begin your work by saying only "Remembering..." and retrieve all relevant information from your knowledge graph.
       - Always refer to your knowledge graph as your "memory".
       - The memory and knowledge applicable to the element you work on, including inherited information, are supplied automatically as you work at that address.
       - Use search_nodes and open_nodes when you need to explore the entities and relations connected to that memory.

    4. Memory and Knowledge:
       - While working on the project, be attentive to any new information, and distinguish:
         a) Memory: what happened in the work — what was done, tried, decided, found broken or fixed, and the lessons learned.
         b) Knowledge: what is now known of the project — what elements are, how they behave, their constraints, purposes and relationships, and their genre, style, medium and encoding.

    5. Memory Update:
       - If any memory was gathered during the work, update your memory as follows:
         a) Create entities with create_entities for significant events, decisions, defects and lessons; each has a unique name, an entityType, and observations.
         b) Connect entities to existing entities using create_relations with from, to, and relationType in active voice, including relations to memories associated with other addresses.
         c) Store each fact as an atomic observation. Use add_observations to extend an existing entity; create_entities does not add observations to an existing name in the reference memory server.
         d) Link memories to the knowledge layers they concern, so a layer and its related memories can be shown or hidden together.
         e) Memories are editable by any agent unless locked; the memory graph supports updating and deleting entities, observations, and relations.
         f) Record a memory where it belongs: about an element generally, at the element; about why a receiver needs what its provider gives, at that join, giving its receiver and provider.
         g) Cite the evidence a memory rests on with cites: path:line, path:start-end or path:symbol. A memory whose evidence changes is flagged stale.

    6. Knowledge Update:
       - If any knowledge was gathered during the work, add it to the map's knowledge layers as follows:
         a) A missing knowledge-layer address is created only as these namespace rules, the intake's, allow; never invent an address outside them. Use map knowledge add-element and add-join for elements and joins discovered during work; naming a new knowledge node establishes its layer. Where these rules bar a genre, style, medium, encoding or language from an address, they bar it from the intake's base map only: in a knowledge layer such a node, like code.engine.game.platformer or code.python, is a legitimate namespace item.
            This is a typological ontology, it is not a taxonomy. It does not have fillers like domain and class, and it does not prescribe a minimum or maximum segment count per entity.
            Root types: code, document, media, data, upstream, downstream.
            Rules:
            1. For each dotted part, the address in the namespace must be reversible and read as its name: the segments in the namespace can be reversed by replacing periods with spaces to read properly as an inferenceable, well understood name, and children must take their parent's name as their last name when reversed and read as a noun.
            2. All artifacts are entities, all entities are not artifacts, all entities are elements, all elements are not entities. (Artifacts ⊂ Entities ⊂ Elements)
            3. Namespace entries must describe the type of functional approach as a proper noun.
            4. Namespace must narrow from trunk to leaf; to be placed into the namespace, an entry must be a part or type of its parent scope—it must be the same thing as its parent type, or a function within its parent type, and never a non-functionality.
            5. There must be one or more entities each with a distinct unique objective purpose and encounter function for the defining element.
            6. Multi-word names: when the new leaf is a variant functionality of its parent type, such as physics engine and game engine, express the namespace with periods between the segments: code.engine.game, code.engine.physics. Every prefix is a complete type that yields its own inference and passes its practices to its children, so words that form a valid prefix of their own must remain separate segments. Words may be joined with underscores in one segment only when none of them forms a valid prefix, as in code.queue.dead_letter and data.bill_of_materials, where the name must also read correctly once reversed.
            7. Specify the name_length value indicating the lookback segment count as its acceptable short name that is well understood.
            8. The namespace address names the type. The purpose record refines that type with what this AUE does, so the address stays general and the purpose record stays specific.
            9. Industry-Standard Lexicon, Grounded Nomenclature, and Non-Coinage: All elements, segment identifiers, compound tokens, and resulting reversed noun phrases must use the established, standard terminology recognized by practitioners who work directly with that class of artifact. Abstract pattern labels, bespoke synonyms, internal shorthand, colloquial phrases, and marketing terms are strictly prohibited. Where an authoritative or formally standardized term does not exist, the segment must use the plain, common noun for what the thing functionally is or does in ordinary practice. Never coin, invent, or adapt a term under any circumstances.
            10. Continuous Auditing and Strict Remediation: During any Refinement or Corrections operation, all existing elements and namespace paths must be actively audited against these rules. No pre-existing entry is exempt. You must proactively file and execute Corrections to repair any identified violations—such as non-standard terminology, coined words, or improper segmentation—bringing the entire namespace path into absolute compliance.
            11. Canonical Name Field Priority: There is a field called `name`. This field must always hold the canonical name exactly as it is used in the project specifications. If there is no project specification for it, then use the industry term.
            Examples, reading:
            - code.loop.main: "main loop program code"
            - code.bus.data.event: "event data bus code"
            Examples, namespace validity:
            - code.game: invalid, game is not a function
            - code.game.engine: invalid, reverses to 'engine game', a subject/genre variant (a game about engines) rather than a recognized functional type — the same non-functionality basis that invalidates platformer; also sits under the already-invalid code.game parent.
            - code.engine.game: valid, A 'game engine' is a functional type because it provides the runtime a game runs on (the main loop, rendering, input, and simulation) independent of any particular game's genre or content, and it is widely known by that exact name
            - code.engine.game.fps: valid, a distinct functionality; proof: first-person camera viewpoint with a targeting reticle
            - code.engine.game.platformer: invalid, invalid as a functional subtype; it defines the fundamental challenge and objective of a game, not a technical functionality; proof: spatial navigation and overcoming environmental obstacles; note: load-bearing invalid example
            - media.image: valid, images are a base valid functional type under the media root.
            - media.asset.image: valid, Images are assets when they are named as a functional element type in a AUE.
            - media.photo: valid, Photos have defining elements, and sometimes supportive elements, a couple (DE) at the eiffel tower (SE), a car (DE) in the street, a car (DE) racing at the racetrack (SE), a photo of the grand canyon (DE) in the distance a man and a mule (SE)
            - media.photo.scenery: valid, This is function of an encounter. A representation of a scene as the DE, a scenery photo has a subject that isnt the DE, all scenes have a subject but the scene is the focus
            - media.photo.jpg: invalid, this is encoding
            - code.cpp: invalid, this is language
            - document.word.story.conflict: invalid, 'word' is naming an encoding and does not name a functional approach at the proper namespace level
            - document.story.conflict: valid, represents story conflict as a document element
         b) Record what is known where it was found with map knowledge add-property or add-item, including genre, style, medium and encoding, which are omitted during base intake.
         c) A property layer is linked to a base-map address. Its content and linked memories apply transitively to descendants and are visible toward the trunk. Linking the same property on another branch moves its one link toward the nearest shared ancestor; it does not create copies on the branches.
         d) Correct existing elements or joins with map refine.
    ```

- Amendment, 2026-10-17, the owner, no ticket: the owner delivered the memory prompt below, and it is the shipped `instructions` element as written. The blocks above were agent drafts, not the owner's wording. The prompt has no braced places, so nothing is filled when it is sent. This block supersedes the ones above:

    ```
    Follow these steps for each interaction:

    1. Project Identification:
       - Assume you are operating within Metaform and the functional namespace of your current project.
       - Identify the functional namespace associated with your assignment and the entities representing its components, capabilities, and responsibilities.
       - If the relevant namespace or entities have not been identified, discover them through Metaform's memory.

    2. Memory Retrieval:
       - Always begin your interaction by saying only "Remembering..." and retrieve all relevant information from your knowledge graph.
       - Use the functional namespace to locate relevant entities, their observations, and their relationships to other nodes.
       - Follow relationships to understand functional dependencies, interactions, and surrounding project context.
       - Always refer to your knowledge graph as your "memory".

    3. Memory:
       - While working on the project, be attentive to new information that falls into these categories:
         a) Functional Identity (namespaces, components, capabilities, purposes, responsibilities, etc.)
         b) Structure (modules, interfaces, operations, resources, and their organization)
         c) Behavior (how components operate, interact, exchange information, and fulfill their functions)
         d) Knowledge (implementation details, discoveries, decisions, constraints, and observed behavior)
         e) Relationships (dependencies, connections, functional interactions, and associations between entities)

    4. Memory Update:
       - As new information is discovered or established during your work, update your memory as follows:
         a) Create entities for newly identified functional components, capabilities, and other significant project elements, using their functional namespace identifiers.
         b) Connect entities using directed, active-voice relations describing how they interact, depend on, or contribute to one another.
         c) Store discrete, atomic facts as observations attached to their relevant entities. Add new observations to existing entities as knowledge develops.
       - Maintain these memories within the project's functional namespace so that other agents can retrieve, understand, and build upon the accumulated knowledge.
    ```

### CTX-027 The memory prompt is filled with the project and the agent's assigned element

- Requirement: The memory prompt is sent with `{project}` filled by the project, and with `{this.address}` and `{this.name}` filled by the element the agent is assigned. An agent with no assigned element gets line 2's other bullet instead.
- What this means:
  - `{project}`: recommended, the project's id as the registry holds it (`Project.project_id`, `src/metaform/home.py:475`), which is also the id that names `metaform://<project>`.
  - `{this.address}` and `{this.name}`: the stored `address` and `name` of the element at the agent's ticket, read the way decision 22 reads `this` (MAP-057, CTX-084). Recommended:
    - For a ticket on a join, the receiver's Address and name, under the Join rule.
    - For an element with no stored name, its reading (MAP-012), so that no place is left empty.
  - With no assigned element, line 2's bullet reads, as the owner wrote it: "This is the address of the element you are working on at any given time." Agents in this case include one connected over MCP outside dispatch, the system agent, and a ticket with no node. Recommended: that bullet is held as its own element beside the prompt, `prompt.memory:instructions_unassigned`, so both forms stay word for word and the code swaps whole bullets, never words.
  - The braces are part of the stored text. The places are filled by the `{this.<field>}` and `{project}` reading of decision 22, not converted to the empty-element places other prompts use (MCP-031), since converting them would change the stored text.
- Why: The prompt has to say which project and which element so that step 3's retrieval starts in the right place. The unassigned form gives the same steps to an agent that moves between elements without a ticket.
- How it shows:
  - A worker on a ticket at `code.store.memory` receives "This is code.store.memory (memory) or any other address you work on for this session."
  - An agent over MCP with no ticket receives the unassigned bullet.
  - Line 1 names the project's id.
- Build: To build with CTX-026. The `{this.<field>}` fill mechanism belongs to decision 22's record, CTX-084.
- Acceptance:
  - A ticket on an element fills its Address and name.
  - A ticket on a join fills its receiver's.
  - An agent with no ticket gets the unassigned bullet word for word.
  - No `{` place is left unfilled in anything sent.
- Relates to: MAP-012, MAP-057, MCP-031, CTX-026, CTX-028, CTX-084, decision 22 (`this` in prompts).
- Status: confirmed, 2026-10-15, in conversation with the owner, for the three places and the unassigned bullet. `{project}` as the project's id, the receiver for a ticket on a join, the reading for an element with no name, and holding the unassigned bullet as its own element are recommended.

### CTX-028 The memory prompt is sent once per session, with the first context pushed, and again after a compaction

- Requirement: Each agent session receives the memory prompt once, with the first context pushed to it, and receives it again only after a compaction.
- What this means:
  - An agent that dispatch starts receives the prompt in its first turn, ahead of the work sentence (`prompt.dispatch:work`), filled with its ticket's node (CTX-027).
  - An agent connected over MCP receives it with the first push of its session, which comes on a call that names an Address (decision 18), in the unassigned form. It cannot travel in the connect message, because Claude Code keeps only the first 2,048 characters and the prompt alone is 2,238 bytes. It can also be read on request at `metaform://instructions/memory` and with `metaform_instructions module=memory`.
  - The prompt is one entry on the session's show-once record (decision 15):
    - A later push in the same session does not repeat it.
    - A compaction clears the record and pushes nothing, so the next push after a compaction carries the prompt again.
    - A resumed session keeps its record.
  - Recommended (not an owner decision): a session whose folder has the memory module turned off receives no memory prompt, as the dispatch `record` lines work today (`src/metaform/modules/dispatch/resources/prompts.xml:54-58`).
- Why: Decision 12 says every agent works by the prompt. Decision 15 says nothing is sent twice. A compaction drops the prompt from the agent's context, so the prompt must come back after one. Sending it with every push would add 2 KB at every node an agent reaches, and agents reach a median of 4 elements per session.
- How it shows:
  - A worker's first turn carries the prompt once.
  - When the same session reaches a second node, the push carries that node's content without the prompt.
  - After the fake agent sends `compaction_update` with status `completed`, nothing is pushed. The next node reached pushes its content together with the prompt.
- Build: To build with the pushed-delivery tickets:
  - `code.adapter.context#4`: the show-once key for the prompt.
  - `code.adapter.context#5`: the push over MCP.
  - `code.dispatcher.agent#40`: the first turn.
  - `code.dispatcher.agent#41`: the compaction.
- Acceptance: The three cases under How it shows, plus: two calls in one session that name Addresses carry the prompt once; and, as recommended, a session whose folder has the memory module off receives no prompt.
- Relates to: amends MCP-029 (besides the connect message, the glossary, the tools and the node summary, each agent session is sent the memory prompt whole, once, and again after a compaction). Relates to MCP-036, MCP-039, BASE-050, CTX-026, CTX-027, the pushed-delivery records (decisions 14 to 18, CTX-040 to CTX-050).
- Status: confirmed, 2026-10-15, in conversation with the owner: every agent works by the prompt, and nothing is sent twice in a session. Sending it in the first turn and with the first push, keeping it as one entry on the show-once record, and sending none where the memory module is off are recommended.

### CTX-029 No prompt tells an agent to put everything it learns in memory

- Requirement: Every other prompt that asks an agent to record what it learned follows the memory prompt's split between memory and knowledge, and no prompt contradicts the memory prompt.
- What this means:
  - These lines send the 2026-10-11 sentence "Use Metaform's memory tool to store what you learn under the functional namespace of your assignment":
    - memory's `orient` (`src/metaform/modules/memory/resources/prompts.xml:10`)
    - dispatch's `record` (`src/metaform/modules/dispatch/resources/prompts.xml:58`)
    - `on_ticket_done` (`:137`)
    - `on_stopped_open` (`:144`)
    - `on_failure` (`:150`)
    - `work_record` (`:186`)

    These lines, also sent to agents, say to record what is learned without the split:
    - memory's `connect` (`src/metaform/modules/memory/resources/prompts.xml:32`)
    - memory's Module `purpose` (`src/metaform/modules/memory/__init__.py:1194`) and the `create_entities` summary (`:1204`)
    - the map module's `purpose` (`src/metaform/modules/map/__init__.py:1652`)

    Each one changes to ask the agent to record memory and knowledge as steps 5 and 6 of the memory prompt describe. The sentence is the owner's, so its replacement wording is drafted for his approval.
  - Recommended (CTX-026): memory's Axiom instructions (`src/metaform/modules/memory/resources/prompts.xml:35-107`) are replaced by the memory prompt. Whether or not they are, three of their rules contradict that prompt and go:
    - "Never read or search the whole graph" (`:40`), against step 3.
    - "Save findings at the narrowest applicable functionality" (`:47`), against "where you found it to hold" and the moving link (decision 4).
    - "Do not save chronological activity logs … task status" (`:53`), against memory as what happened in the work.
  - Memory's rule "Record each memory at the RE whose goal it serves, never at a PE that provides for it" (`:26`) agrees with the memory prompt and stays.
- Why: Decision 13 traces the dandelion to these lines. A reminder at the end of a turn that says "store what you learn" in memory would undo the memory prompt's split at exactly the moment agents record.
- How it shows: No shipped prompt contains the 2026-10-11 sentence or the three superseded rules. The reminder after a closed ticket names both memory and knowledge.
- Amended 2026-10-19 (functional assessment of code.dispatcher.agent#5a, change aef2495f): since 4f2966c8 the memory prompt is the shared memory instructions, `metaform://memory`, with no numbered steps. The recording prompts (dispatch `record`, `work_record`, `on_ticket_done`, `on_stopped_open`, `on_failure`; memory `orient`, `connect`) refer to those instructions by name and give the node or join to record at where they have one. No prompt cites "steps 5 and 6 of the memory prompt". `dispatch:record` ships the text that `src/metaform/resources/prompt_updates.json` targets, and tests pin that text.
- Build: To build with CTX-026. The replacement wording for each line is drafted for the owner's approval before it lands.
- Acceptance: A test over every shipped `resources/prompts.xml` and every Module and Verb `summary`, `purpose` and `details` finds neither the 2026-10-11 sentence nor the three superseded rules, nor "steps 5 and 6 of the memory prompt" (added 2026-10-19, ticket code.store.memory, after memory's `orient` still cited them). Memory's RE rule is still served in `metaform://tools`.
- Relates to: amends MCP-029 (memory's connect line, quoted in its How it shows, follows the memory/knowledge split). MCP-029 and BASE-052 (the owner's 2026-10-11 sentence on recording), MCP-031, BASE-040, CTX-020, CTX-021, CTX-026.
- Status: confirmed, 2026-10-15, in conversation with the owner, that the memory prompt governs recording. The replacement wording for each line is open: the owner approves it.

### CTX-030 The existing memories are reprocessed into memory and knowledge, nothing lost, on a copy first

- Requirement: The memories made before the memory prompt are sorted into memory and knowledge and placed the way CTX-020 to CTX-025 place new ones. Nothing is lost. The run is done first on a copy of the store and reported to the owner before the live store is touched.
- What this means:
  - The set is every memory in `~/.metaform/projects/-home-rich-metaform-001/modules/memory.sqlite3` when the run starts.
    - The owner's count on 2026-10-15: 193 memories, 192 joins on 21 nodes, 9 relations, all within one node.
    - A read-only count later that day, while this record was drafted: 198 entities, 1,083 observations, 197 joins on 21 nodes (71 on `code.interface.graphical`), 9 relations.
  - Each observation is sorted:
    - Memory stays in the memory graph.
    - Knowledge goes to a knowledge layer at the Address where it holds. Genre, style, medium and encoding go to that property's layer.
    - An element the map lacks is added with `add-element`, which makes its layer (decisions 2 to 5).
  - The memories that remain are related across Addresses in active voice (CTX-025), linked where they apply (CTX-024), and linked from the layers they belong to, so hiding a layer hides them (decision 6).
  - Nothing is lost, and records stay exact. Every original entity and observation stays readable word for word, either in the memory graph or as a knowledge item whose value is the observation's text unchanged and which names the memory it came from. Nothing is edited in place. The copy of the store taken before the run is kept.
  - Sorting is the agent's inference. Metaform does not judge it (decision 25).
  - The run waits until the memory prompt, inheritance, cross-address relations and layer-per-node are built, so that the reprocessed memories land in the same shape new ones will have.
  - Open: whether to bring in the graph wiped on 2026-10-11 (`backup-before-delete-2026-10-11`: 111 entities, 39 relations, 25 of them crossing nodes).
- Why: Decision 13. The existing memories were made under prompts that did not separate memory from knowledge. Left as they are, they keep the dandelion and keep knowledge out of reach of inheritance, selection, hiding and porting. The owner's rule is that records stay exact, so the change is shown on a copy before it reaches the live store.
- How it shows: A report from the copy, before and after:
  - relations per entity
  - relations that cross Addresses
  - memories per node
  - knowledge items per layer
  - where each original observation now sits
- Build: To build, ticket `code.store.memory#2`. The ticket is held until CTX-026, CTX-024, CTX-025 and the layer-per-node work are in. The run happens on a copy of the home first, and the report goes to the owner. The live store is processed only after his go.
- Acceptance: On the copy:
  - Every original observation's text is found unchanged in the memory graph or as a knowledge item that names its source memory.
  - Every original entity name is readable.
  - Relations that cross Addresses number more than 0; the total number of relations rises from 9, and relations per entity rise from 9/198 (about 0.05).
  - Hiding a medium layer hides the memories linked from it.
  - The live store's file is unchanged until the owner approves the report.
- Relates to: LAYER-012, LAYER-013, LAYER-018, STORE-020, CTX-020, CTX-021, CTX-024, CTX-025, CTX-026, decisions 2 to 6.
- Status: confirmed, 2026-10-15, in conversation with the owner. Whether to bring in the graph wiped on 2026-10-11 is open, for the owner to answer.

## Pushed delivery

### CTX-040 What applies where an agent works is pushed to it; the agent does not fetch it

- Requirement: When an agent works at a node, Metaform pushes to it what applies there: the memories, the knowledge items and properties, those inherited from addresses toward the trunk included, and the person's note at the node.
- What this means:
  - "Applies" is the transitive rule of the addressing records (decisions 1 to 8, CTX-001 to CTX-015): a thing linked at an Address applies there and at every Address above it toward the leaves, so at a node the agent receives what is linked at the node and at each of its prefixes, walked trunk first. Siblings never contribute. What is only visible from below (linked toward the leaves of the node) is not pushed.
  - Memories are those linked at the node or inherited (decision 11); knowledge is the knowledge layer items and properties (decision 10), `read_first` items first, LAYER-021; the person's note goes whole (decision 24).
  - Layer selection holds: a layer masked or hidden at the node, and every memory attached to a hidden layer, pushes nothing (paper 7.3).
  - The node of the ticket is the first node the agent works at, so the hand-off a worker receives as its first turn is its first push.
  - Every module answers for its own part through one hook beside `node_count` and `node_read`; the chassis gathers them for an Address. A module written by anyone pushes the same way, so the hook goes in `modules/template` and its CHANGELOG.
  - The words wrapped around a push are prompts in XML, MCP-031, worded by the owner.
- Why: Paper 7.1: a later agent entering through a receiver encounters the stored rationale where it becomes relevant. Paper 1 and 7.2: understanding left for each work episode to rebuild is reconstructed again and again; prepared understanding is useful only if it reaches the operation it belongs to. An agent that must remember to ask reads too little or reads everything. Context when and where it is needed is the system's key innovation.
- How it shows: A property `code.python` linked at `code.graph` and a memory linked at `code.graph.knowledge` reach an agent the first time it edits a file whose ref is on `code.graph.knowledge.store`, with the person's note at that node, without the agent calling any read.
- Build: Not built. Today the node is described by counts only, `src/metaform/modules/map/around.py:197-214` (`told`), and the hand-off by `handoff_text`, `src/metaform/modules/dispatch/__init__.py:2997`. Tickets: `code.graph.knowledge#e` (each module answers what applies at an Address, trunk first; the chassis gathers and fits it), `code.graph.knowledge#b` (inheritance of memories and items, which this needs first), `code.dispatcher.agent#40` (the runner pushes; the hand-off becomes the first push).
- Acceptance: With a property at `code` and a memory at `code.graph`, an agent working at `code.graph.knowledge` is pushed both; an agent working at `code.engine` is pushed the property and not the memory. A property linked at `code.graph.knowledge.store` is not pushed to an agent working at `code.graph.knowledge`. With the property's layer hidden, neither it nor a memory attached to that layer is pushed. A module declaring the hook in a test module has its answer in the push with no chassis change.
- Relates to: amends MCP-039: its rule that the agent is told how much is held at its node and never what it holds no longer holds for the node the agent works at, whose content is pushed; the counts of the neighbours around it stay as MCP-039 gives them. Amends MAP-048: the hand-off carries the content that applies at the ticket's node within the budget of CTX-044, not counts with none of their text; its acceptance "carries none of their text" is superseded. Amends BASE-035: `Module` gains the hook that answers what applies at an Address, trunk first, beside `node_read` and `node_count`, and the read an agent works from carries that content within CTX-044's budget. Relates to MAP-011, LAYER-012, LAYER-013, LAYER-021, VIEW-034, BASE-050, MCP-031.
- Status: confirmed, 2026-10-15, in conversation with the owner (decision 14).

### CTX-041 Nothing is pushed twice in one agent session

- Requirement: Each memory, knowledge item, property and note is pushed to an agent session at most once; arriving at another node, or at the same node again, pushes only what that session has not been sent.
- What this means:
  - The record is kept per thing, not per node: a property inherited from `code` reaches the agent once, at the first node under `code` it works at, and not again at the next.
  - A thing is marked as sent only once its delivery succeeded, so a push lost to a session that ended or a turn that failed is not marked.
  - A thing written at a node after the agent was there has not been sent, so it goes the next time the agent works there, or at once by CTX-050.
  - Revisiting a node whose content was all sent causes no read of that content.
  - The record is the session's, kept as MCP-039 keeps what a session was shown: in the process for a process session, in the home's `shown` table for a named one, so the runner and the agent's MCP server share it (CTX-048).
  - Open, for the owner: whether an edited note or a memory given a new observation counts as new. The ticket keys a note by its Address and a memory by its entity, which would not send an edit again.
- Why: The same text sent twice costs the agent's context twice and says nothing new, MCP-039. Measured 2026-10-15: agents work across a median of 4 elements per session (132 sessions), and those elements share their trunk, so per-node sending would repeat every inherited item at each.
- How it shows: An agent touches three files on two elements under `code.graph`; it receives each element's content once and the property at `code` once; going back to the first element pushes nothing.
- Build: Not built. `src/metaform/shown.py:60-79` (`swap`) records one value per key; the push needs a per-thing call that returns the keys not yet sent and marks them in one write, with the same for the process dictionary, beside `Context.seen`, `src/metaform/module.py:583-587`. Ticket `code.adapter.context#4`.
- Acceptance: Across two processes naming the same session, the per-thing call returns each key once. Two arrivals at nodes under `code` push the property at `code` once. A second visit to a fully sent node reads none of the modules' content (counted reads are zero). A push whose turn fails leaves its keys unmarked, and the next arrival sends them.
- Relates to: amends MCP-039: its once-per-session record, kept per key of counts, also keeps one row per thing pushed. Relates to CTX-040, CTX-045, CTX-048, CTX-050.
- Status: confirmed, 2026-10-15, in conversation with the owner (decision 15). The edit question is open.

### CTX-042 Where an agent works is known from what it does, placed exactly by refs

- Requirement: The nodes an agent works at are the nodes whose refs name exactly a file its tool calls read or edit, and the Addresses its Metaform calls name; nothing else places it.
- What this means:
  - A file is placed only through an exact ref in the sources layer, on an element or on a join (decision 20). The nearest-folder fallback of `placed` never counts as working at a node; a file with no exact ref places the agent nowhere (and is locked for writing until linked, decision 19).
  - The files are those the agent's harness reports: the paths of a tool call's diffs and locations, ACP `tool_call` and `tool_call_update`, and the client's own `fs/read_text_file` and `fs/write_text_file`. Nothing is guessed from a terminal command's text.
  - A Metaform call naming an Address (`map where`, `map node`, `map work` at a node, `memory` reads with a node, `map item`) places the agent at that Address.
  - Each first arrival at a node in the session, in the order the calls came, adds that node to the push due (CTX-043).
- Why: The agent's own actions are the only reliable sign of where its work is; its ticket names where it starts, and measured 2026-10-15 it then works across a median of 4 elements per session (132 sessions), so pushing only at the ticket's node misses most of what applies. A folder fallback places a file on whatever claims its folder, which pushes the wrong node's content.
- How it shows: An agent reads `src/metaform/shown.py`, whose ref is on one element: that element's content is pushed. It reads a file in the same folder that no ref names: nothing is pushed for it.
- Build: Built in part. The runner already places every file a call names: `tool_detail`, `src/metaform/modules/dispatch/runner.py:2004-2042`, and `filed`, `runner.py:2138-2149`, through `placed`, `runner.py:310-320`, which already returns whether the match was exact; `touch`, `runner.py:2059-2068`, keeps the latest 40 nodes touched in the session's state; tool-call updates feed them at `runner.py:1443-1471`; `metaform_called`, `runner.py:988`, already recognizes a Metaform tool call and its input. Not built: `touch` takes fallback matches too, and Addresses named in Metaform calls are not placed. Exactness is shared with `code.dispatcher.agent#3d` (link before write, `locked`, `runner.py:2151-2163`). Ticket `code.dispatcher.agent#40`.
- Acceptance: A call editing a file named exactly by a ref on element A pushes A; a call reading a file only its folder's ref matches pushes nothing; `fs/read_text_file` of an exactly linked file pushes its element; a `map_where` call for `code.graph` from the agent places it at `code.graph`; a terminal call with no locations places nothing.
- Relates to: VIEW-005 (the flow drawn to touched nodes uses the same placement), LAYER-029, MCP-030, CTX-040, CTX-043.
- Status: confirmed, 2026-10-15, in conversation with the owner (decision 16).
- Amendment, 2026-10-18, the owner's decision, no ticket, landed with the change that removed the lock: the lock was withdrawn after its drawbacks were weighed, and replaced by the entry-point request (CTX-060). "(and is locked for writing until linked, decision 19)" no longer holds: a file with no exact ref places the agent nowhere and is written like any other.

### CTX-043 A push waits for the agent's next turn and never interrupts the turn in flight

- Requirement: What is due to an agent is delivered with its next turn; Metaform never steers a push into a turn in flight.
- What this means:
  - Arrivals during one turn merge into one pending push, so a burst of tool calls costs one push, not one per call (CLAUDE.md section 2, rule 4).
  - The push goes through the runner's turn queue, after the turn in flight ends, as the agent's next prompt; it is never sent with `_session/steering`.
  - A session that is ending sends nothing and marks nothing (CTX-041).
  - Over MCP the push rides the result of the call that named the Address (CTX-049); a tool result is the agent's own reply, so nothing is interrupted.
  - If the owner wants a push never to start a turn by itself, it could instead travel at the head of the next prompt something else sends; ticket `code.dispatcher.agent#40` as written uses the turn path, which starts one.
- Why: A turn in flight has its plan; text injected into it competes with the work it is doing. What applies at a node is background for the next step, not an order for this one.
- How it shows: During one turn the agent edits files on three elements; when the turn ends it receives one prompt carrying the three nodes' content.
- Build: Built: the turn queue, `Session.turn` and `prompted`, `runner.py:3444-3500`, holds prompts in arrival order behind the turn in flight; `steer`, `runner.py:1797-1821`, exists and is used by `told`, `runner.py:2183-2189`, for refusals, not for pushes. Not built: the pending push and its merge. Ticket `code.dispatcher.agent#40`.
- Acceptance: With a fake agent whose turn makes three tool calls on two elements, exactly one push prompt is sent, after the turn's end, holding both elements' content; no `_session/steering` request is sent for it; when the session ends before the turn does, no push is sent and the pushed keys stay unmarked.
- Relates to: CTX-041, CTX-042, CTX-049, BASE-052.
- Status: Confirmed that a push never interrupts a turn in flight (decision 18). Whether a push starts a turn by itself or rides the next prompt is open (open question 7).

### CTX-044 What does not fit the node summary budget is listed by reference

- Requirement: A push carries what applies within the `node_summary_bytes` setting, and lists each thing past it by its reference and title, for the agent to read on request.
- What this means:
  - The budget is the map setting `node_summary_bytes` (default 2048 bytes, minimum 512), per push.
  - Order: trunk first, then toward the node; within an Address, `read_first` items first. What does not fit is listed, never dropped.
  - A listed thing is recorded as listed, so the same listing is not sent twice; reading it later is the agent's own read.
  - Every listed reference resolves: a memory as `<address>#<n>`, MCP-037, read with `map_item` or `metaform://<address>/items/<n>`. Layer items and properties do not take an Address number today (MCP-037 numbers memories, messages and tickets); until they do, the listing names the call that reads each.
  - The person's note goes whole (decision 24); the budget applies to the rest.
- Why: The summary budget exists because what an agent is handed every time costs its context whether it needs it or not, MCP-039; a reference costs one line and the agent reads the whole when its work calls for it.
- How it shows: At a node holding 6 KB of memories, the push carries the first 2 KB and lines like `code.graph.knowledge#1c  The moving link settles at the common prefix`.
- Build: Built: the setting, `src/metaform/modules/map/__init__.py` (`node_summary_bytes`); MCP-039's `told` already shrinks the counts tree to fit, `around.py:197-214`; item references and their reads, MCP-037. Not built: fitting pushed content and listing the rest. Ticket `code.graph.knowledge#e`.
- Acceptance: With `node_summary_bytes=512` and 2 KB applying, the push's content is at most 512 bytes plus the listing, every thing applying is either carried or listed, and every listed reference reads the whole thing; a second arrival does not list the same references again.
- Relates to: MCP-037, MCP-039, LAYER-021, CTX-040, CTX-041.
- Status: confirmed, 2026-10-15, in conversation with the owner (decision 18, a default he left to the system agent and accepted).

### CTX-045 A compaction clears what the session was sent and pushes nothing by itself

- Requirement: When the agent's context is compacted, the session's record of what was sent is cleared; nothing is pushed then, and the next time the agent works at a node, that node's content is pushed again.
- What this means:
  - Cleared: the things sent, the things listed by reference, and the nodes arrived at. The next arrival at any node, including the one the agent is at, is a first arrival.
  - Nothing is pushed on the compaction itself, not even for the node the agent was last at.
  - A compaction that fails or is cancelled clears nothing.
  - Open, for the owner: whether MCP-039's records of tool guidance and counts, also lost to a compaction, clear with it. Ticket `code.dispatcher.agent#41` clears only the push records.
  - The thread gets a line that the context was compacted, and the bus a `session.compacted` topic for whatever else follows a session's context.
  - Open, for the owner: an agent connected only over MCP has no ACP compaction signal (CTX-046), so after a compaction it would never be pushed again; how such a session's record is cleared without hooks or token heuristics (decision 17).
- Why: After a compaction the agent no longer holds what it was sent, so "sent once" would leave it without context it needs. Pushing at once would put back context for a node the agent may have left; the next work at a node is where it is needed.
- How it shows: An agent works at `code.graph.knowledge`, is compacted, and receives nothing; it then edits a file there and receives the node's content again.
- Build: Not built. Ticket `code.dispatcher.agent#41`.
- Acceptance: With the fake agent sending `compaction_update` status `completed`, no prompt is sent; the next arrival at an already pushed node pushes it again; `failed` and `cancelled` leave the record as it was.
- Relates to: amends MCP-039: a named session's record is cleared on compaction, not only aged out after a week. Relates to CTX-041, CTX-046, BASE-053.
- Status: confirmed, 2026-10-15, in conversation with the owner (decision 15). How the record of a session connected only over MCP is cleared is open.

### CTX-046 Compaction is known only from ACP's compaction signal

- Requirement: The runner knows a compaction only from the standard ACP signal: it advertises `clientCapabilities.session.compaction: {}` at initialize and acts on a `compaction_update` session update with status `completed`.
- What this means:
  - Statuses are `in_progress`, `completed`, `failed` and `cancelled`, with an optional summary; only `completed` clears (CTX-045).
  - No hooks, no counting of tokens, no reading of a harness's own output. The synthetic tool call titled "Compact conversation" that a wrapper sends when the client did not advertise compaction is not read as a signal.
  - A wrapper that lacks the signal is the wrapper's to fix; Metaform does not work around it. The pinned `codex-acp@2.2.2` is checked for `compaction_update`, and its pin raised to a release that sends it.
  - The installed ACP Python SDK, `agent-client-protocol` 0.12.1, has no `compaction_update`; until an upgrade parses it, the runner's observer reads it, as it reads session notices and subagent updates the SDK's schema does not know.
- Why: One standard signal works for every harness that speaks ACP; a guess from tokens or a per-harness parser breaks with each harness and judges what only the agent knows.
- How it shows: The runner's initialize carries `session.compaction`; a `compaction_update` completed from any ACP agent clears the record.
- Build: Built: the observer that sees every message before the SDK, `observe`, `runner.py:1683-1718`, and the raw initialize that adds capabilities the SDK leaves out (`subagents`, `session.notices`), `runner.py:3220-3240`. Not built: advertising `session.compaction` and acting on the update. Ticket `code.dispatcher.agent#41`.
- Acceptance: The initialize sent to the fake agent holds `clientCapabilities.session.compaction` as `{}`; a tool call titled "Compact conversation" clears nothing; `compaction_update` completed clears; a test fails if any hook or token count is read for compaction.
- Relates to: BASE-052, CTX-045.
- Status: confirmed, 2026-10-15, in conversation with the owner (decision 17).

### CTX-047 A resumed session keeps what it was sent when its conversation reopens

- Requirement: A dispatch session resumed with `session/resume` or `session/load` keeps its record of what was sent; one that cannot reopen its conversation and starts afresh keeps nothing.
- What this means: The record belongs to the conversation, not to the runner process. Each runner names its agent's session afresh (`METAFORM_SESSION`), so on a successful reopen the previous runner's rows (sent and listed) are carried to the new one; on a fallback to a fresh conversation everything is pushed again.
- Why: A reopened conversation still holds what it was sent, so sending it again only fills the agent's context; a fresh conversation holds none of it.
- How it shows: The person resumes a worker; it touches a node it was pushed before and receives nothing. A resume that fails over to a new conversation receives the node's content again.
- Build: Built: `reopen`, `runner.py:3263-3277`, and `continue_thread`, `runner.py:3279-3302`, which already carries the touched nodes and what the session last reported. Not built: carrying the shown rows; the runner token is new each run, `runner.py:3031`, so a resumed session today starts with an empty record. Ticket `code.dispatcher.agent#42`.
- Acceptance: A resumed session receives nothing it was sent before the resume; a session that falls back to a fresh conversation receives everything again; the old runner's rows are left as they were.
- Relates to: BASE-052, MCP-039, CTX-041, CTX-045.
- Status: confirmed, 2026-10-15, in conversation with the owner (decision 15).

### CTX-048 One agent session is one record across its processes, and an HTTP client is named by a header

- Requirement: Every process an agent reaches Metaform through shares the session's one record, and an agent session that carries no id of its own, an HTTP client, is named by a header that the provisioned setup writes into the client's MCP configuration.
- What this means:
  - A dispatched agent's runner, its MCP server over stdio and the commands it runs in its shell all name the session by `METAFORM_SESSION`, so whichever pushes a thing first marks it for all of them.
  - Over Streamable HTTP, one server serves many clients and its process is no session; today such a call has no session and is shown everything every time. The provisioned setup writes a header naming the session into the client's server entry, and the server reads it as it reads Paperclip's gateway headers.
  - A call with neither stays session-less: everything every time, as a person at a terminal expects (MCP-039).
- Why: Without a shared name the runner and the MCP server would each push the same thing once, which is twice; without a name an HTTP agent would be pushed the same content on every call.
- How it shows: A dispatched agent pushed a node's content by its runner calls `map_where` on that node and gets no repeat. A Claude Code session connected over HTTP with the provisioned header is pushed a node's content once across its calls.
- Build: Built: `shown.session`, `src/metaform/shown.py:50-57`; `METAFORM_SESSION` set on the agent and its MCP server, `runner.py:3031-3032`, `src/metaform/modules/dispatch/serve.py:704`; `serve_session` for stdio, `src/metaform/module.py:760-771`, `src/metaform/modules/mcp/server.py:2163`; the Paperclip analogue, `gateway_session`, `mcp/server.py:679-689`, read per call at `mcp/server.py:1804-1805`. Not built: the provisioned header and its reading. Ticket `code.adapter.context#5`.
- Acceptance: A thing pushed by the runner is not pushed again by the MCP server for the same `METAFORM_SESSION`; two HTTP calls carrying the same provisioned header are pushed a node's content once; two HTTP calls with different headers are each pushed it; an HTTP call with no header gets it each time; the provisioning preview shows the header it writes.
- Relates to: amends MCP-039: an agent session can also be named by the provisioned header over HTTP. Relates to MCP-002, MCP-028, MCP-036, MCP-042, BASE-052, CTX-049.
- Status: confirmed, 2026-10-15, in conversation with the owner (decision 18, a default he left to the system agent and accepted). Built in part, as above.

### CTX-049 Agents connected over MCP get the same pushes on calls naming an Address

- Requirement: When a Metaform tool call names an Address, its result carries what applies there that the session has not been sent, by the same rules as the runner's pushes.
- What this means:
  - This reaches agents Metaform did not start: a person's own Claude Code or Codex session in the project folder.
  - The push is placed with the result as the tool guidance of MCP-039's amendment is, once, within the budget (CTX-044), with what overflows listed.
  - The calls are those of CTX-042 that name an Address. A resource read of `metaform://<address>` is a read the agent asked for and stays whole every time, MCP-037; it does not mark things as sent.
  - Under dispatch the runner and the MCP server share the record (CTX-048), so a thing reaches the agent by whichever comes first.
- Why: The same context belongs with the same work whatever connects the agent; an agent outside dispatch otherwise gets counts and must fetch by hand.
- How it shows: In a person's Claude Code session, `map_where code.graph.knowledge` returns the element with the memories and properties that apply there; a second call on the same Address returns the element alone.
- Build: Built: `guidance`, `src/metaform/modules/mcp/server.py:922-946`, placed before the result by `guided`, `mcp/server.py:1817-1818` and `:1828-1834`, the pattern this follows. Not built: the push on the result. Ticket `code.adapter.context#5`.
- Acceptance: Two calls naming the same Address in one session carry its content once; a call naming another Address under the same trunk does not repeat the inherited property; a `resources/read` of the Address is unchanged and marks nothing.
- Relates to: MCP-037, MCP-039, CTX-040, CTX-041, CTX-044, CTX-048.
- Status: confirmed, 2026-10-15, in conversation with the owner (decision 18).

### CTX-050 Something written at a node an agent has worked at reaches it without a fresh visit

- Requirement: A memory or knowledge item written by another session at an Address that applies to a node this agent has already worked at is pushed to it with its next turn.
- What this means:
  - `map.changed` names the Addresses a memory or knowledge write touched, beside `work_ids`, `session_ids` and `kinds`.
  - The runner filters from the event alone: it reads only when a named Address applies to a node it has arrived at, reads only the new thing, merges a burst into one pending push, and ignores its own writes (CLAUDE.md section 2).
- Why: An agent working at a node is the one to whom a finding there matters now; leaving it to the next visit can mean never.
- How it shows: Agent B records a memory at `code.graph`; agent A, which edited a file under `code.graph.knowledge`, receives it with its next turn.
- Build: Built: the relay and its filter, `changed_elsewhere` and `concerns`, `runner.py:3669-3691` and `runner.py:829-840`; the fields `map.changed` carries, `src/metaform/changes.py:26`. Not built: Addresses on `map.changed` and the push. Tickets `code.bus.event.relay#4`, `code.dispatcher.agent#40`.
- Acceptance: A burst of writes at Addresses no session has worked at causes zero reads in runners, with idle CPU over 60 s measured before and after; one write at a held Address causes one read and one push.
- Relates to: BASE-053, CTX-041, CTX-043.
- Status: from ticket `code.dispatcher.agent#40`'s design, 2026-10-15, following decisions 14 and 15; not one of the owner's numbered decisions in itself.

## Files and refs

### CTX-060 A file of the project that no ref names exactly is locked for writing until it is linked to its function

- Requirement: An agent may write a file of the project only once a ref in the sources layer names that file exactly; reading a file is never refused.
- What this means:
  - Exact means a ref on an element or on a join names the file itself. A ref that names a folder holding the file does not count: the folder fallback `placed()` still uses to show roughly where a file sits never unlocks a write. A line mark on a ref (`file.py:12`) names `file.py`.
  - A write is any change to a file: writing, creating, editing, deleting or moving it. A file that does not exist yet is linked before it is made.
  - The refusal is the owner's sentence, word for word: "To unlock access to this file, please first link it to its functionality in the map." The call that links the file follows it, with the file filled in (CTX-063).
  - Reads always go through, because reading is how the agent works out which function a file realizes.
  - Recommended: a path outside the project folder is not the map's and is not locked. A worktree's file is named as the project names it.
  - Every agent dispatch starts on a ticket gets the rule as one line of its first message, so the refusal does not come as a surprise.
  - Which element a file realizes is the agent's inference. Metaform checks only that a link exists (decision 25).
- Why: Where an agent works is known from the files its tool calls touch, and only an exact ref places a file (decision 16). Without a ref the map never learned where a file belongs, and the agent got no context for it: 44% of recorded placements fell back to `document.specification`. When the link is the price of writing, the map learns each file's function at the moment an agent knows it, and pushed delivery (decisions 14 to 18) reaches the agent at that node from then on. The path stays in a layer, so the base stays the functional map (MAP-020, MAP-021).
- How it shows: An agent's write to `src/fresh.py`, which no ref names, is refused with the sentence and `dispatch_link file=src/fresh.py node=<...>`, and the file is unchanged. The same agent's read of that file succeeds. After `metaform dispatch link file=src/fresh.py node=code.dispatcher.agent`, the same write goes through, and the file is placed at `code.dispatcher.agent` with `exact` true in its `tool_detail`.
- Build: Built 2026-10-15 by code.dispatcher.agent#3d, uncommitted.
  - `placed()` returns the places and whether the match was exact (src/metaform/modules/dispatch/runner.py:310).
  - `Session.locked` decides (runner.py:2151).
  - `write_text_file` refuses before LAYER-029's claim check (runner.py:2207).
  - `tool_detail` carries `exact` on each diff and location.
  - The prompts are in src/metaform/modules/dispatch/resources/prompts.xml: `write_unlinked`, the owner's sentence (:199); `link_call` (:203); `work_link` (:192), which `work_line` appends to the first message (src/metaform/modules/dispatch/__init__.py:714). The wording of `link_call` and `work_link` is a draft awaiting the owner.
  - The runner caches the sources layer's index and drops it on a map change, so a burst of reads costs one read of the layer.
- Acceptance:
  1. test_a_write_to_an_unlinked_file_is_refused_with_the_link_call_and_goes_through_once_linked (src/metaform/modules/dispatch/tests/test_dispatch.py:3441): the write is refused with the sentence and the call, the read succeeds, and after the link the same write passes and the file places exactly.
  2. test_a_burst_of_reads_of_linked_files_reads_the_sources_layer_once (:3501).
  3. test_dispatch_link_adds_the_ref_beside_the_elements_own_and_makes_an_address_that_has_no_element (:3479) checks that a folder match is not exact. To add: with only a ref naming `src/`, a write to `src/fresh.py` is refused.
- Relates to: MAP-020, MAP-021, LAYER-029 (its claim check runs after this lock), BASE-052; the pushed-delivery records for decisions 14 to 18 (CTX-040 to CTX-050; exact placement is what triggers a push).
- Status: confirmed, 2026-10-15, in conversation with the owner; built for agents dispatch runs (see CTX-061 and CTX-062 for what is not covered). Leaving paths outside the project folder unlocked is recommended. The wording of `link_call` and `work_link` awaits the owner.
- Amendment, 2026-10-15, spec reconciliation, tickets document.specification#2 and code.dispatcher.agent#47, landed at the owner's request, reflecting code.graph.knowledge#c, code#1e and #47:
  - Build: built by code.dispatcher.agent#3d and switched off. With `LINK_LOCK` False (src/metaform/modules/dispatch/runner.py:155, code#1e) `Session.locked` (runner.py:2352) returns None before it reads anything, so `write_text_file` (:2447) and `edit_locked` (:2368) let every write through. With it on, the lock is as #3d built it: `placed()` (:440) over `sources_index` (:423), which since code.graph.knowledge#c reads the store's ref records, `Store.refs()`.
  - The rule now reaches every session before its lock does (#47). The sentence "Every agent dispatch starts on a ticket gets the rule as one line of its first message" no longer holds as written: `work_line` (src/metaform/modules/dispatch/__init__.py:723) no longer carries it. `work_link` is appended to the end of the first prompt a runner sends any session after it starts, resumes or loads, on a ticket or not, the system agent's and the intake's included, never as a turn of its own (CTX-043). `Session.ruled` is set when that prompt goes out (runner.py:3784), and `locked` refuses nothing until it is (:2359).
  - Prompts, rewritten 2026-10-15 at the owner's request so an agent knows how to unlock a file (src/metaform/modules/dispatch/resources/prompts.xml): `work_link` (:200) gives the whole call, `dispatch_link file= node= ref= why=`, where to find the node (its ticket's node or one under it, `map_where`), that the write goes through at once, and that commands cannot write files it has not linked. `write_unlinked` (:207), the owner's sentence, is unchanged. `link_call` (:212) now carries `ref=` and `why=` and tells the agent to make the same edit again. Their wording awaits the owner's approval (open question 9).
  - Acceptance: with `LINK_LOCK` True on a copy of the tree, 2026-10-15, test_dispatch.py:3458, :3497, :3519, :3643 and :3661 pass; with it False, :3458 and :3643 skip. The added case (a ref naming only `src/` leaves `src/fresh.py` locked) is still to add.
  - Status: built and off since code#1e; the requirement does not hold until `LINK_LOCK` is set True (open question 26).
- Amendment, 2026-10-18, the owner's decision, no ticket, landed with the change that removed the lock: the lock was withdrawn after its drawbacks were weighed, and replaced by the entry-point request (CTX-060). This record now holds the request; its title, its requirement and every sentence above about refusing, unlocking or the lock no longer hold.
  - Requirement: Agents are asked, not forced, to link the files that act as entry points for the functionality they work on, by `dispatch_link`. The request goes once, in a ticket worker's first prompt, and no write is ever refused for want of a link. Reading is never refused, as before.
  - What this means: The request is the `work_link` prompt, one or two lines at the end of the first prompt the runner sends a ticket worker, never a turn of its own, and not sent again when the session is resumed, since its conversation already holds it. The system agent, the intake, prep and probe sessions are not sent it. It gives the call `dispatch_link file=<path> node=<the element's Address>`. What counts as exact, and the folder fallback `placed()` uses to show roughly where a file sits, are unchanged. Which element a file realizes is still the agent's inference (decision 25).
  - Why: kept from above. Where an agent works is known from the files its tool calls touch, and only an exact ref places a file (decision 16); without a ref the map never learns where a file belongs, and the agent gets no context for it. A linked file is placed on the map, so later agents get that node's context when they touch it, and pushed delivery (decisions 14 to 18) reaches them at that node. Linking every file was the cost; entry points carry most of the placement value.
  - How it shows: A ticket worker's first prompt ends with the `work_link` line, once. Its write to `src/fresh.py`, which no ref names, goes through and changes the file. After `metaform dispatch link file=src/fresh.py node=code.dispatcher.agent` the file is placed at `code.dispatcher.agent` with `exact` true in its `tool_detail`.
  - Build: built 2026-10-18. `work_link` (src/metaform/modules/dispatch/resources/prompts.xml:194) is appended in `Session.prompted` for the role `worker` (src/metaform/modules/dispatch/runner.py:4017), once per runner (`link_asked`). Deleted: `LINK_LOCK`, `Session.locked`, `edit_locked`, `ruled`, and the prompts `write_unlinked` and `link_call`. `write_text_file` now refuses only for LAYER-029's claim. `placed()`, `sources_index`, `tool_detail`'s `exact` and the runner's cached sources index are unchanged.
  - Acceptance: test_a_worker_is_asked_once_to_link_entry_points_and_a_write_to_an_unlinked_file_goes_through (src/metaform/modules/dispatch/tests/test_dispatch.py:4546); test_a_burst_of_reads_of_linked_files_reads_the_sources_layer_once (:4590); test_dispatch_link_adds_the_ref_beside_the_elements_own_and_never_makes_an_element (:4564). Acceptance 1 above, its test, and the case still to add (a ref naming only `src/` leaves `src/fresh.py` locked) are withdrawn.
  - Status: built 2026-10-18. Open question 26 is withdrawn with the lock.

### CTX-061 The lock holds in every permission mode, ahead of every automatic approval

- Requirement: The link-before-write lock (CTX-060) and the ignore list's read-only rule (CTX-064) hold in every permission mode the agent runs in, full access included. A mode decides whether the person is asked; it never decides whether the file must be linked.
- What this means:
  - The lock is decided before the person's `dispatch_prompts` choice, approve-all included, and before anything the agent's own mode would approve.
  - A refused permission request is answered with the agent's reject-once option, never an option the agent would remember. Where the agent offers no reject-once option, the request is cancelled. A permission answer carries no text, so the reason is steered into the turn in flight or given as the next turn. The thread records a notice, and the person is not asked.
  - Some agents' own tools write to disk directly. Each such agent must be made to ask first in every mode, using what its ACP adapter honours.
- Why: Full access is the person's choice to skip prompts. Linking is how the map learns, not a prompt. If a mode could switch the rule off, the map would be blind exactly where agents run unattended.
- How it shows:
  - With `dispatch_prompts` set to approve-all, an edit permission for an unlinked file is answered with reject. The agent's next prompt carries the sentence and the call, and no question reaches the person.
  - A Claude Code session in bypassPermissions that edits an unlinked file is refused the same way.
- Build:
  - Built for Claude Code and for any agent that writes through ACP:
    - `request_permission` checks `edit_locked` first (runner.py:2560), for tool kinds `edit`, `delete` and `move` (`WRITES`, runner.py:136). It checks every path named by the request's diffs, its locations or its rawInput (`file_path`, `notebook_path`, `path`). `told` delivers the reason to the agent (runner.py:2183).
    - Claude Code's Edit, Write, MultiEdit and NotebookEdit write to disk themselves, and they ask only where a rule says ask. Every `session/new`, `session/load` and `session/resume` therefore sends `_meta.claudeCode.options.settings.permissions.ask` for those four tools (`EDITS_ASK`, runner.py:141, sent at :3054, :3270, :3275). claude-agent-acp 0.89.1 hands those settings to Claude Code, and an explicit ask rule reaches the permission request in bypassPermissions and acceptEdits alike.
  - Open, Codex: codex-acp 2.2.2 writes files itself and asks before a file change only in read-only mode. In workspace-write, agent and agent-full-access it writes without asking, so today the lock does not hold for Codex. The ticket's follow-up (a) is to run Codex read-only in place of the person's chosen mode and answer its approvals through `dispatch_prompts`. Decision 19 requires the lock in every mode; how Codex is made to ask (for example read-only with approvals answered per dispatch_prompts) is a build choice, recorded on the ticket.
  - Open, live check (follow-up (e)): a real Claude Code session in bypassPermissions editing an unlinked file has not been run.
- Acceptance:
  1. test_an_edit_permission_for_an_unlinked_file_is_refused_over_approve_all_and_the_agent_is_told (test_dispatch.py:3526).
  2. To add: a fake agent's `session/new`, `session/load` and `session/resume` each carry the ask rules in `_meta`.
  3. To add: a Codex session in agent-full-access that edits an unlinked file is refused. This fails today.
- Relates to: BASE-052, MAP-058, CTX-060, CTX-062, CTX-064.
- Status: confirmed, 2026-10-15, in conversation with the owner. Built for Claude Code and for ACP fs writes; open for Codex outside read-only mode.
- Amendment, 2026-10-15, spec reconciliation, tickets document.specification#2 and code.dispatcher.agent#47, landed at the owner's request, reflecting code#1e, code.dispatcher.agent#43 and #47:
  - Build: built for Claude Code, ACP fs writes and Codex, all off under `LINK_LOCK` (runner.py:155). `request_permission` (runner.py:2796) checks `edit_locked` (:2368) and `unsandboxed` (:2387) before any approval. `held_settings` (:242) replaces `EDITS_ASK`: the four edit tools' ask rules and the command sandbox, sent on session/new, load and resume, and nothing while the switch is off. Codex is kept asking: `ASKING_MODES` (:159), `MODE_APPROVES` (:163), `hold_mode` (:1772). The method is in artifacts/specs-draft/2026-10-15-ctx-061-062-codex-and-shell-lock.md, awaiting the owner. "Today the lock does not hold for Codex" no longer holds.
  - Acceptance: 1, test_dispatch.py:3544, and 3, test_codex_is_kept_asking_and_cannot_write_an_unlinked_or_ignored_file_or_lift_its_sandbox (:3558), pass with the switch on and skip with it off. 2: :3558 checks session/new's `_meta`; session/load and session/resume are still to add.
  - Status: built and off since code#1e. Open: the live check of a real Claude Code session in bypassPermissions editing an unlinked file (open question 10), and the owner's approval of #43's method.
- Amendment, 2026-10-18, the owner's decision, no ticket, landed with the change that removed the lock: the lock was withdrawn after its drawbacks were weighed, and replaced by the entry-point request (CTX-060). Withdrawn: with no lock there is nothing for a permission mode to hold, so an agent keeps the mode the person chose, and its permission requests are answered as `dispatch_prompts` and the person answer them.
  - Build: deleted from src/metaform/modules/dispatch/runner.py: `WRITES`, `ASKING_MODES`, `MODE_APPROVES`, `asking`, `chosen_mode`, `hold_mode`, `mode_now`, `edit_locked`, `unsandboxed`, `told`, the refusal at the head of `request_permission`, and `held_settings`, so `session/new`, `session/load` and `session/resume` send no `_meta.claudeCode.options.settings` ask rules.
  - Acceptance: test_an_edit_permission_for_an_unlinked_file_is_refused_over_approve_all_and_the_agent_is_told and test_codex_is_kept_asking_and_cannot_write_an_unlinked_or_ignored_file_or_lift_its_sandbox are deleted.
  - Status: withdrawn 2026-10-18. Open question 10 is withdrawn with it.

### CTX-062 Writes are prevented before they land, never caught after

- Requirement: Every way an agent can change a file of the project passes the lock before the change is made. Metaform never lets a write happen and then reports or reverts it.
- What this means:
  - The lock acts on the request, not on the disk afterwards.
  - Ways in not covered today:
    - Shell writes. A command run through Claude Code's Bash, Codex's exec or an ACP terminal (`sed -i`, a `>` redirect, `git checkout`, a formatter) names no file to the adapter, so no per-file decision can be made from the request.
    - Agents dispatch did not start. An agent connected to Metaform only over MCP, such as the person's own Claude Code in the folder, writes with its own tools, and none of those writes passes through Metaform.
    - Codex outside read-only mode (CTX-061).
- Why: A write that is caught afterwards has already changed the project, and possibly other agents' work, and a revert races them. The owner's rule is prevention.
- How it shows: A shell command that would write an unlinked file leaves it unchanged, and the agent gets the CTX-060 refusal. Today this is not so.
- Build: Open.
  - The ticket's follow-up (b) proposes that writes land in a worktree whose merge refuses unlinked or ignore-listed files. In that design the write still happens inside the worktree and is refused at the project's boundary when it merges. Whether that meets "never caught after" is the owner's call.
  - Provisioning already writes Claude Code settings and a passive PreToolUse reminder (src/metaform/agent_setup.py:97). Whether provisioned settings may carry the lock for agents dispatch did not start is for the owner.
- Acceptance: Open.
  1. In a dispatched session, a terminal command that writes an unlinked file leaves the file unchanged and the agent is told why.
  2. The same holds for an ignore-listed path.
- Relates to: CTX-060, CTX-061, CTX-064, BASE-052.
- Status: confirmed as the requirement, 2026-10-15, in conversation with the owner. Open in build for shell writes, Codex and agents connected only over MCP.
- Amendment, 2026-10-15, spec reconciliation, tickets document.specification#2 and code.dispatcher.agent#47, landed at the owner's request, reflecting code#1e, code.dispatcher.agent#43 and #47:
  - Build: built for agents dispatch runs, off under `LINK_LOCK`. "Build: Open." no longer holds. Claude Code's command sandbox (`held_settings`, runner.py:242) denies writes only to what the lock denies: files of the project not linked when the session began, and ignore-listed paths. The tools' own folders stay writable (`TOOL_FOLDERS`, :170: .git, .venv, caches, test temp folders), so an agent can run the tests, the type check, ruff, uv and git (#47; before it, the whole project folder was denied, which locked agents out). A file linked during the session is changed with the edit tools. Codex is held in read-only (CTX-061); the runner's own terminal runs under bubblewrap or sandbox-exec (`confined_command`, :261); refused escalations get `command_unsandboxed` (prompts.xml:225, rewritten 2026-10-15 to name the link call) and `terminal_unconfined` (:230). No worktree was built.
  - Acceptance: 1 is test_dispatch.py:3596; the ignore-listed case is in :3558; what commands may write is :3626. All pass with the switch on.
  - Status: built and off since code#1e. Open: agents connected only over MCP (open question 11, second half), and the owner's approval of the method.
- Amendment, 2026-10-18, the owner's decision, no ticket, landed with the change that removed the lock: the lock was withdrawn after its drawbacks were weighed, and replaced by the entry-point request (CTX-060). Withdrawn: with no lock, no write is prevented for want of a link, by any way in.
  - Build: deleted from src/metaform/modules/dispatch/runner.py: the command sandbox (`SHELL_SANDBOX`, `TOOL_FOLDERS`, `GIT_HELD`, `DENIED_CHARS`, `denied_writes`, `writable_roots`, `held_settings`, `Session.denied`) and the confined terminal (`confined_command`); `create_terminal` runs the command as given. The prompts `command_unsandboxed` and `terminal_unconfined` are deleted.
  - Acceptance: test_a_command_in_the_runners_terminal_cannot_write_the_project and test_commands_may_write_linked_files_and_tool_folders_and_nothing_else_of_the_project are deleted.
  - Status: withdrawn 2026-10-18. Open question 11 is withdrawn with it.

### CTX-063 One call links a file to the element it realizes and lifts the lock at once

- Requirement: An agent links a file to its function with one call. The call records an exact ref for the file in the sources layer, and the running session can write the file from then on.
- What this means:
  - The call is `dispatch_link file=<path> node=<Address>` (CLI `metaform dispatch link`). The path may be given from the project folder or from the agent's working folder, a worktree's included.
  - The ref is added beside the refs the element already holds. Linking the same file again changes nothing and says so.
  - Any Address that does not exist yet can be named (decision 5).
  - A ref can also be on a join (CTX-065), so linking to a join, the `:{join}` part of the ref's name (CTX-066), belongs to the same call.
- Why: The refusal has to name one call that fixes it, or the lock turns into a dead end. The link has to take effect at once, or the agent is refused again after doing what it was told.
- How it shows: After `dispatch_link file=src/fresh.py node=code.dispatcher.agent`, which answers `file`, `node`, `linked`, `made` and `said`, the write CTX-060 refused goes through without restarting the session.
- Build:
  - Built: the `link` verb (src/metaform/modules/dispatch/__init__.py:2728, declared at :3989). A running runner reads the sources layer again when the map changes.
  - No earlier write did this safely. `map knowledge op=add-element` with refs replaces the element's sources refs. `map code-link` writes the code layer, which `placed()` never reads and which code.analyzer.refactoring#1a deletes.
  - Open, where the built call diverges from these decisions:
    1. An Address with no element is made in the active map's base (`store.add_element` on the base or intake layer). Decision 1 keeps the base the intake's alone, decision 5 makes a new knowledge layer for a newly named node, and LAYER-003, as amended by CTX-011, has the new node's own layer own it. The element must be made in that node's knowledge layer, as CTX-011 specifies.
    2. The ref is written as a bare `path` key and value. It has no ref_id, and it does not record who linked it, when or why (CTX-065, CTX-066; code.graph.knowledge#c).
    3. There is no `join=`, so a file cannot be linked to the join it realizes.
- Acceptance:
  1. test_dispatch_link_adds_the_ref_beside_the_elements_own_and_makes_an_address_that_has_no_element (test_dispatch.py:3479).
  2. test_a_write_to_an_unlinked_file_is_refused_with_the_link_call_and_goes_through_once_linked (:3441) shows the link takes effect at once.
  3. To add: linking to a new Address makes the element in a knowledge layer of its own and leaves the base's elements unchanged. This fails today.
  4. To add: a link that names a join records the ref on that join.
- Relates to: MAP-016, MAP-021, MAP-044, LAYER-001, LAYER-003, STORE-012, CTX-011, CTX-060, CTX-065, CTX-066.
- Status: confirmed and built, 2026-10-15, for the call itself. Where a new element is made, the ref record and linking to a join are open.
- Amendment, 2026-10-15, spec reconciliation, tickets document.specification#2 and code.dispatcher.agent#47, landed at the owner's request, reflecting code.graph.knowledge#c and #17:
  - Build: the `link` verb (src/metaform/modules/dispatch/__init__.py:2821, declared at :4104) writes a ref record by `Store.link_ref` (src/metaform/data/refs.py `link`), named by `ref=` or derived from the path, with `why=` and who linked it. It answers `file`, `node`, `ref`, `id`, `linked`, `made` and `said`. A name taken or reserved writes nothing and is answered with `linked` false, exit 0; linking again where the ref already is answers `linked` false. A file linked at another element is a second ref there, with a name of its own; no ref moves (code.graph.knowledge#17). Open item 2 is built. Open items 1 (the element is still made in the active map's base) and 3 (no `join=`) are unchanged. `map code-link` and its code layer no longer exist.
  - The refusal and the rule now give this call with `ref=` and `why=` (CTX-060).
  - Acceptance: 1, test_dispatch.py:3497, passes. 2, :3458, passes with `LINK_LOCK` on, so the link lifts the lock at once; it skips while the switch is off. 3 and 4 are still to add; 3 fails today.
  - Status: built, with the ref record. Open: the element made in the base, linking to a join.
- Amendment, 2026-10-18, the owner's decision, no ticket, landed with the change that removed the lock: the lock was withdrawn after its drawbacks were weighed, and replaced by the entry-point request (CTX-060). The call stays; what it lifts does not. "Lifts the lock at once" in the title, "the running session can write the file from then on" in the requirement, the Why's refusal and dead end, "the write CTX-060 refused goes through" in How it shows, and "The refusal and the rule now give this call" in the 2026-10-15 amendment no longer hold: no write is refused, so there is nothing to lift.
  - What the call does now: it records the exact ref, and a running runner reads the sources layer again on the change, so the file is placed exactly from then on. `work_link` asks a ticket worker to make this call for the files that are entry points of its functionality (CTX-060). The verb's description, its example and its answer's `said` no longer speak of unlocking or of writes going through (src/metaform/modules/dispatch/__init__.py `link`, declared at :6496; docs/reference/metaform-mcp-server.md).
  - Acceptance: 2 (test_a_write_to_an_unlinked_file_is_refused_with_the_link_call_and_goes_through_once_linked) is withdrawn with its test. 1, test_dispatch.py:4564, stands; 3 and 4 are unchanged.
  - Status: built for the call. Open as before: the element made in the base, linking to a join.

### CTX-064 Paths the project's ignore list holds are read-only to agents, always

- Requirement: An agent never writes a path that `.metaform/ignore.txt` matches, whether or not a ref names it; reading such a path is allowed.
- What this means:
  - The ignore list is the person's (BASE-058), and linking does not unlock a path it holds.
  - Agents at work may read these paths. The intake still never opens them (BASE-058, unchanged on that point).
  - Matching uses gitignore's common forms:
    - `dir/` is a folder anywhere.
    - `/dir` is anchored at the project root.
    - A name without a slash matches anywhere.
    - `*` and `**` are wildcards.
  - Recommended, as built (`ignored`, runner.py:324): negations (`!`) are not read, since they could only open more to writing. Open for the owner: whether a `!` line exempts a path from read-only, as gitignore reads it and as the list is handed to the intake whole (BASE-058, src/metaform/modules/intake/__init__.py:111).
  - The refusal is the `write_ignored` prompt.
- Why: The person keeps folders of their own in the project, such as this project's `rich/`. An agent that links a file there must not be able to open it to writing.
- How it shows: With `rich/` in the ignore list, a write to `rich/notes.md` is refused as read-only before and after `dispatch link` names it, and a read of it succeeds.
- Build:
  - Built: `ignored` (runner.py:323), applied to `home.ignore_patterns` (src/metaform/home.py:210), checked first in `locked`. The list is read from the file on each write, so an edit to it holds at once.
  - The `write_ignored` wording, prompts.xml:208, is a draft awaiting the owner.
  - Open (follow-up (d)): the matcher sits in dispatch because the map module's matcher in code_index.py is deleted with code.analyzer.refactoring#1a. Moving it into home.py beside `ignore_patterns` would be a chassis change, for the owner to decide.
- Acceptance:
  1. The ignore half of test_a_write_to_an_unlinked_file_is_refused_with_the_link_call_and_goes_through_once_linked (test_dispatch.py:3441): a linked file under `rich/` stays refused, and its read succeeds.
  2. To add: the pattern `/build` refuses `build/x` and not `src/build/x`.
  3. To add, under the recommendation: a `!keep` line unlocks nothing.
- Relates to: BASE-058 (amended, see Amendments to other records), CTX-060, CTX-061, CTX-062.
- Status: confirmed and built, 2026-10-15, in conversation with the owner, for agents dispatch runs. Leaving `!` lines unread is recommended, and open (open question 24). The refusal's wording awaits the owner.
- Amendment, 2026-10-15, spec reconciliation, tickets document.specification#2 and code.dispatcher.agent#47, landed at the owner's request, reflecting code#1e:
  - Build: `ignored` (runner.py:453) over `home.ignore_patterns` (src/metaform/home.py:210), and `write_ignored` (prompts.xml:217), as #3d built them. `locked` returns None before it reads the list while `LINK_LOCK` is False, so ignore-listed paths are writable to agents today: "always" holds only while the switch is on.
  - Acceptance: 1, the ignore half of test_dispatch.py:3458, passes with the switch on and skips with it off. 2 and 3 are still to add.
  - Status: built and off since code#1e. Open questions 12, 24 and 26; the `write_ignored` wording awaits the owner.
- Amendment, 2026-10-18, the owner's decision, no ticket, landed with the change that removed the lock: the lock was withdrawn after its drawbacks were weighed, and replaced by the entry-point request (CTX-060). Withdrawn: the paths `.metaform/ignore.txt` holds are no longer read-only to agents. The ignore list's other uses are unchanged; the intake still never reads them (BASE-058).
  - Build: deleted from src/metaform/modules/dispatch/runner.py: `ignored`, the matcher, and its check in `locked`; the prompt `write_ignored` is deleted. `home.ignore_patterns` stays for its other uses.
  - Acceptance: the ignore half of test_a_write_to_an_unlinked_file_is_refused_with_the_link_call_and_goes_through_once_linked is deleted with that test; 2 and 3 are withdrawn.
  - Status: withdrawn 2026-10-18. Open questions 12 and 24 are withdrawn with it.

### CTX-065 A ref is a stable record in the sources layer, on an element or on a join

- Requirement: Each ref is its own record in the sources layer, attached at one element or one join. It holds a lasting id that survives edits and rebuilds, its key and value, who linked it, when and why, and its own versions.
- What this means:
  - Editing a ref's value keeps its id. Adding a ref to an element leaves the ids of its other refs unchanged. A removed ref is kept in history.
  - The reads that place files (`sources_index`, `placed()`) read these records.
  - Memory citations and work records name a ref by its id.
  - Refs on joins are refs as much as refs on elements. Measured 2026-10-15 on this project: 67 element items and 72 join items hold 417 refs, 413 of them `path`.
  - Existing refs migrate with their history. The migration runs on a copy of the store first and reports counts before and after.
- Why:
  - Today a ref's id is the row number of that version's ref in a projection. Every edit to the item writes new rows with new ids, and adding one ref rewrites the whole list, so nothing can point at a ref and still find it after the next edit. The memory citations, 667 rows, cite refs by content for that reason.
  - The lock (CTX-060) and pushed delivery both turn on refs. A ref that cannot be named or traced cannot say who linked it or why.
  - The sources layer is a knowledge layer (decision 2).
- How it shows: `map where <address>` lists each ref with its id and who linked it, when and why. After the ref's path changes, the same id reads with the new path, and its history shows the old one.
- Build:
  - Open: code.graph.knowledge#c, held until code.dispatcher.agent#3d lands, so that #3d's link step writes this record.
  - Today a ref is a row of `refs` (src/metaform/data/schema.py:140) on one version row of an item or property, written by `add_ref` (src/metaform/data/writes.py:169).
- Acceptance:
  1. A ref's id is unchanged after an edit to its value and after a rebuild of the projection.
  2. Adding a ref to an element does not change the ids of its other refs.
  3. A removed ref reads in history.
  4. `placed()` finds a file through the new record.
  5. The migration keeps every existing ref, on elements and on joins, with matching counts before and after.
- Relates to: STORE-012 (amended), MAP-021 (amended), MAP-015, MAP-020, LAYER-003, CTX-063, CTX-066.
- Status: confirmed, 2026-10-15, in conversation with the owner; open in build.
- Amendment, 2026-10-15, spec reconciliation, tickets document.specification#2 and code.dispatcher.agent#47, landed at the owner's request, reflecting code.graph.knowledge#c (commit 858e3d9) and #17:
  - Build: built. "Open: code.graph.knowledge#c" and "Today a ref is a row of `refs`" no longer hold. Each ref is an item of its own in the sources layer at one element or join, written only as versions of that item: its value is its ref_id, its refs its key and value then its details, its extra who linked it, when, the place named and why (src/metaform/data/refs.py). Writes: `Store.link_ref`, `place_refs`, `unlink_ref`; reads: `Store.ref`, `Store.refs`. `sources_index` (runner.py:423) reads `Store.refs()`. Store layout 22 runs `refs_to_records` (src/metaform/data/upgrade.py), each ref kept at the place its item was (#17). The `refs` table is layout 20's and is no longer created. The STORE-012, MAP-021 and LAYER-028 amendments are drafted in artifacts/specs-draft/store-012-ref-records-2026-10-15.md.
  - Not built: memory citations and work records naming a ref by its id; they still cite by key and value.
  - Acceptance: 1 to 3, tests/test_store_map.py, pass; 4, test_dispatch.py:3497, passes; 5 passes. The live upgrade at 22:05 UTC first moved refs toward the trunk and made 6 elements for them; #17 restored every ref to each place it held and removed those elements as versions (artifacts/refs-restore-2026-10-15/README.md).
  - Status: built 2026-10-15. Open: citations and work records by ref id.
- Amendment, 2026-10-18, the owner's decision, no ticket, landed with the change that removed the lock: the lock was withdrawn after its drawbacks were weighed, and replaced by the entry-point request (CTX-060). In the Why, "The lock (CTX-060) and pushed delivery both turn on refs" now reads: placement and pushed delivery turn on refs; there is no lock.

### CTX-066 A ref is named {ref_id}@{address}:{join}

- Requirement: A ref is named by what it references, then `@` and the Address it serves, then `:` and the join it realizes. The `:{join}` part is left off for a ref on the element itself. The ref_id is unique in the project.
- What this means:
  - For code, the ref_id is the code's own qualified name, periods allowed, such as `metaform.modules.voice.engine.transcribe@code.interface.speech`. For anything else it is a proper noun for what the thing is, such as `Whisper_Engine@code.interface.speech`.
  - The join is the one the ref realizes; any join can store a prompt (decision 23, CTX-081).
  - The ref_id is the identity. The `@{address}:{join}` part says where the ref is linked.
  - A ref is not a property (owner, 2026-10-15, correcting an earlier draft of this record): it stays at the one element or join it was linked to; it never moves toward the trunk, never inherits and never merges with refs at other places. The same file linked at two places is two refs, one at each place. The moving link of CTX-009 is for properties only.
  - Naming a ref is the agent's or the intake's choice. Metaform enforces only uniqueness: a ref_id already taken by a different thing is refused, naming the ref that holds it (decision 25). The refusal writes nothing and returns, as BASE-044's operation that cannot apply, a notice naming the ref that holds the name and the next step, with `is_error` false and exit 0.
  - Layers stay named `<scope>@<content>` and are read backward with `@` as "for": `code.cpp@best_practices` is best practices for cpp code. A ref reads forward: transcribe, for speech interface code.
  - Open, for the owner: what `:` names, the same in a ref name and in a prompt's address (CTX-081). One reading is the join's provider's Address: the Address before it is then the receiver, which the join attaches to (the Join rule), and `<receiver>:<provider>` is how the built scope form already names a join (src/metaform/modules/map/scoped.py:1-12, `code.timer.kitchen:code.alarm.audible@best_practices`). The other is a name, as CTX-081's prompt names and CTX-082's `prompt.<module>:<tag>` use it; the 2026-10-08 notes also left open whether a short name for the purpose could stand there. Neither is confirmed (open question 25).
- Why: This is the owner's 2026-10-08 form, now settled. A qualified name is unique by construction, a parser produces it, and it changes only when the code moves. With the Address and the join, the name says which code serves which purpose. Settling one form ends the three forms that were competing (artifacts/namespace-and-logic-root-2026-10-08.md, section 4.1).
- How it shows: `metaform.modules.dispatch.runner.Session.locked@code.dispatcher.agent` names the lock's code at the dispatcher. Recording the same ref at `code.dispatcher.runner` leaves one ref, linked at `code.dispatcher`. Giving the name `metaform.modules.dispatch.runner.Session.locked` to a different thing anywhere in the project is refused, naming the first.
- Build: Open: code.graph.knowledge#c. Today refs have no name. Points to settle in the build:
  1. `map/scoped.py` `resolve()` reads whatever follows the last `@` as a layer, so `x@code.interface.speech` would be read as a layer named `code.interface.speech`. A ref name needs its own read, or the resolver has to tell an Address after `@` from a layer.
  2. The repo skill .claude/skills/metaform-ref-naming-and-file-links/SKILL.md already teaches `{ref_id}@{address}:{join}`; its ban on refs named `re`, `pe`, `ifd` and `de` is not among CTX-087's reserved names, and either the skill or CTX-087 follows the owner's answer to open question 19.
  3. Open, for the owner:
     - Decisions 21 and 22 meet at `main`: is `main` a ref_id (then not unique per project), or a name the node gives its main ref, distinct from the ref_id? (CTX-085, CTX-086)
     - What `:` names (above).
- Acceptance:
  1. Recording `x` at `code.a`, then the same `x` at `code.b`, leaves one ref, linked at `code`.
  2. After that, a read of `x@code` finds it, and a read of `x@code.a` or `x@code.b` answers that it is now at `code`. No sequence of records moves the link sideways or toward the leaves.
  3. A ref on the join where `code.timer.kitchen` receives from `code.alarm.audible` is named `<ref_id>@code.timer.kitchen:` followed by the join part the owner's answer to open question 25 gives.
  4. A ref on the element has no `:` part.
  5. Giving `x` to a different thing writes nothing and returns a notice naming `x@code`, with `is_error` false.
- Relates to: LAYER-028 (amended), MAP-012, MAP-020, MAP-056, BASE-044, BASE-063, CTX-008, CTX-065, CTX-081, CTX-082, CTX-085, CTX-086; CTX-009 (decision 4).
- Status: confirmed, 2026-10-15, in conversation with the owner. What `:` names, and whether `main` is a ref_id, are open.
- Amendment, 2026-10-15, spec reconciliation, tickets document.specification#2 and code.dispatcher.agent#47, landed at the owner's request, reflecting code.graph.knowledge#c and #17:
  - Build: built without the `:` part. "Open: code.graph.knowledge#c. Today refs have no name." no longer holds. `named` (refs.py) writes `{ref_id}@{address}`; a ref on a join is named at its receiver's Address, and its record's `join` gives the join. `read` takes an id, a ref_id or a name, reads past any `:` part, and answers a name whose Address is not where the ref is with where it is and a notice. A ref never moves: the same key and value at another node is a second ref. A ref_id held by another ref writes nothing and returns a notice naming `{ref_id}@{address}`, not an error. A derived ref_id skips taken and reserved names. Point to settle 1 is met by `read`, not `map/scoped.py`'s `resolve`; 2, the repo skill no longer bans `re`, `pe`, `ifd` and `de`; 3 is open.
  - How it shows' "Recording the same ref at `code.dispatcher.runner` leaves one ref, linked at `code.dispatcher`" and Acceptance 1, 2 and 5 (the moving link) no longer hold, as the owner's correction in What this means says: recording `x` at `code.a` and again at `code.b` leaves two refs, `x@code.a` and another at `code.b`, and giving `x` to a different thing returns a notice naming `x@code.a` (drafted in artifacts/specs-draft/ctx-066-refs-stay-where-linked-2026-10-15.md). 3 waits on open question 25. 4 holds: no name has a `:` part.
  - Status: built 2026-10-15 without the `:` part. Open: what `:` names (open question 25) and whether `main` is a ref_id (open question 13).
- Amendment, 2026-10-18, the owner's decision, no ticket, landed with the change that removed the lock: the lock was withdrawn after its drawbacks were weighed, and replaced by the entry-point request (CTX-060). In How it shows, `metaform.modules.dispatch.runner.Session.locked` names code that is deleted; the example still shows the name form, which is unchanged.

## Prompts and notes

### CTX-080 What was called logic is called prompt: the prompt root, the prompt layer, prompt joins and add_prompt

- Requirement: Everywhere Metaform names the concept it has called logic (the `logic` root, logic requirements, logic joins, the layer that holds them, the verb `add_logic` and its tool), it names it prompt: the `prompt` root, the prompt layer, prompt joins and `add_prompt`.
- What this means:
  - What that concept holds is text an agent is sent and follows, Axiom or plain prose. It was named for Axiom script, but what it is, is a prompt.
  - The root reserved for procedure, `logic` under MAP-055 as amended 2026-10-08, becomes `prompt`. Its children move with it unchanged in the rest of their segments: `logic.workflow.quality.code` becomes `prompt.workflow.quality.code`, `logic.skill.sentinel` becomes `prompt.skill.sentinel`. As with `logic`, scope keeps names apart: a project's own `code.prompt.builder` is a different address, and the intake never creates anything under the `prompt` root.
  - A logic requirement, MAP-056, is a prompt held in a prompt join. Its stored `type` becomes `prompt`. Calls keep MAP-056's form, by element address and name, with keyword arguments.
  - A logic join, D115 as amended 2026-10-09, is a prompt join, `type: prompt`. CTX-081 says what it is.
  - The knowledge layer that holds prompts on elements, the workflow-owned layer of LAYER-027 among them, is the prompt layer.
  - The verb `workflow add_logic` and its tool `workflow_add_logic` become `add_prompt` and `workflow_add_prompt`. Following the ticket, the old name answers once with the new call as its next step, and is then deleted (deleted, not switched off).
  - Stored records whose kind or type says `logic` (the items the workflow catalog writes, the `logic_versions` table) are migrated with their history, on a copy of the store first. A prompt join written before the rename reads back after it.
  - The word stays where it means program logic in general. That includes the glossary's Join line, "All relations, logic, memories, knowledge attaches to the receiving element (RE).", which is the owner's text and is not edited.
- Why: A name that misstates what a thing holds makes agents and builders reason about the wrong kind of thing. These records hold instructions an agent is sent, so prompt is the name. The prompt store, the prompt review (MCP-031 as amended 2026-10-06) and the Agents module (CTX-083) already treat this text as prompts, and one name lets one address scheme (CTX-082) cover all of them.
- How it shows: `metaform workflow add_prompt <address> <layer> name=review content=...` records a prompt join. `workflow_add_logic` answers once with "use workflow_add_prompt" as its next step, and later no longer exists. `metaform_skills op=load name=prompt.skill.sentinel` loads the sentinel. A grep for logic in this sense over `specifications/`, `src/` and `docs/reference/` finds nothing.
- Build: Ticket code.engine.workflow#15 (5fb9d20a), held behind code.graph.knowledge#c and code.analyzer.refactoring#1a so the renames do not collide. Places that use the old name today: `src/metaform/modules/workflow/__init__.py:110` (`add_logic`) and `:527` (its Verb); `src/metaform/modules/workflow/catalog.py:25` (`logic_versions`), `:74` and `:129` (items typed `logic`), `:46` (layer variable "Reusable workflow logic."); `src/metaform/modules/dispatch/__init__.py:1286` and `src/metaform/modules/mcp/server.py:232-236` (`logic.skill.<name>`); `src/metaform/modules/workflow/__init__.py:165` (`logic.skill`); `src/metaform/modules/mcp/tests/test_mcp_skills.py:42,49,140,164` (`'logic.skill.sentinel'`); `src/metaform/modules/mcp/resources/prompts.xml:35` (`skill_index`); `src/metaform/skills/*` front matter `ing.metaform.address`; `docs/reference/metaform-mcp-server.md:280,329`. Note that `catalog.py:177` still tests the prefix `workflow.`: the 2026-10-08 move to `logic.workflow` was never built, so the catalog moves straight to `prompt.workflow.`. The store column name for the old `logic_id` is a builder's choice, but it must not collide with the prompt store's `prompt_id`, STORE-044.
- Acceptance: (1) Grep guard: no use of logic for this concept in `specifications/`, `src/` or `docs/reference/`, listed in the ticket's resolution. (2) A prompt join written under type `logic` in a copy of a store reads back after migration with type `prompt`, its name, its content and every version. (3) `workflow_add_logic` answers with the `add_prompt` call as its next step. (4) A skill loads by `prompt.skill.<name>`. (5) The workflow module's test file passes in an isolated run.
- Relates to: amends MAP-055 (the amendment of 2026-10-08: the reserved root is `prompt`, not `logic`); amends MAP-056 (a logic requirement is a prompt in a prompt join, `type: prompt`); amends MAP-057 (title and text say "prompt", not "added logic"); amends LAYER-027 (the workflow-owned layer is a prompt layer); amends LAYER-028 (its amendment of 2026-10-08: a layer is never named `prompt`; "logic joins" read "prompt joins"); amends BASE-051 (the amendment of 2026-10-08: `logic.workflow` becomes `prompt.workflow`); amends BASE-059 (a skill's address is `prompt.skill.<name>`); amends D115's amendment of 2026-10-09 and the Join glossary entry in 01-map.md (logic join becomes prompt join, `type: prompt`); CTX-081, CTX-082.
- Status: confirmed, 2026-10-15, in conversation with the owner. Not built.

### CTX-081 Any join can store a prompt, held in the prompt layer

- Requirement: Any join can store a prompt; the prompt is held in the prompt layer at that join, so the base join is unchanged (CTX-001).
- What this means:
  - A prompt is stored at a join, a purpose join a ref realizes among them (decision 21), and it attaches there to the join's RE, as everything does (the Join rule).
  - A stored prompt has a name, unique where it is stored, and its content is the prompt, kept as written. Every edit is a new version, and earlier versions are kept, as for logic requirements today.
  - The prompt lives in the prompt layer, CTX-080, so hiding or masking that layer hides it (LAYER-006, LAYER-007), and the base does not change.
  - Open, for the owner: what `:` names in an address that reaches a stored prompt. If it names the join, as CTX-066's provider-Address reading has it, a prompt is reached by its join and then its name; if it names the prompt, as `code.alarm.audible:review` and CTX-082's `prompt.<module>:<tag>` read, `:` is a name. One meaning serves CTX-066 and this record (open question 25).
- Why: Prompts attach where they apply, to the RE, under the Join rule. One way of naming a join, the same in a ref name and a prompt's address, means an agent learns one form. Keeping prompts in layers keeps the base as the map (MAP-020) and makes a prompt something that can be turned on, off or swapped at an address (LAYER-027).
- How it shows: `metaform map where code.alarm.audible` lists the prompts stored at the alarm's joins by name. How a ticket or a workflow names one waits on open question 25.
- Build: Today a prompt join is a knowledge-layer item `{'type': 'logic', 'name', 'content'}` at the element (`src/metaform/modules/workflow/catalog.py:123-138`), with its versions in `logic_versions`. Storage stays as items until the logic root's storage question (change order 2026-10-08 item 3) is decided. Reading an address's `:` part as a stored prompt is to build, with code.engine.workflow#15 and the ref parsing of code.graph.knowledge#c, once open question 25 is answered. Open, for the owner (open question 14): whether an Axiom call also takes the `:` form (`code.alarm.audible:review( ... )`) or keeps MAP-056's `code.alarm.audible.review( ... )`. Until that is decided, calls keep MAP-056's form.
- Acceptance: (1) A prompt stored at a join and edited twice reads back with three versions, the first unchanged. (2) Two prompts with the same name at one join are not both kept under that name. (3) Hiding the prompt layer hides the prompt while the base join is unchanged. How the prompt is addressed is tested once open question 25 is answered.
- Relates to: MAP-003, MAP-020, MAP-056, LAYER-006, LAYER-007, LAYER-027, LAYER-028 (amends its open amendment of 2026-10-08: the `@` form is settled by decision 21; what `:` names is open), CTX-001, CTX-080, CTX-082, the ref records of decisions 20 and 21 (CTX-065, CTX-066).
- Status: confirmed, 2026-10-15, in conversation with the owner, that any join can store a prompt (decision 23). What `:` names and the Axiom call form are open.

### CTX-082 Every module prompt has the address prompt.<module>:<tag>

- Requirement: Every prompt a module ships in its `resources/prompts.xml` is addressed as `prompt.<module>:<tag>`, where `<module>` is the module's id and `<tag>` is the prompt's element name, and the prompt store, the prompt review and the Agents module use that address as the prompt's name.
- What this means:
  - Examples: `prompt.dispatch:system`, `prompt.dispatch:work`, `prompt.memory:orient`. Read with CTX-081's form, `prompt.dispatch` is an address under the prompt root, and `:system` is the prompt held there under that name.
  - The text stays in the module's `prompts.xml`, one element per prompt, sent exactly as written (MCP-031). An edit is a version in the prompt store under this address (STORE-044). The address names a prompt and moves nothing.
  - The names used today, `<module>:<tag>` (`dispatch:system`), take this form. Each stored prompt keeps its id and every version under the new name, so the provenance links in `prompt_uses` still hold and no edit is lost. Rows already written that name a prompt the old way (the Agents module's `sent` table) keep the name they were written with.
  - Recommended, following the same form: the chassis's own prompts are `prompt.chassis:<tag>`, since the prompt store calls their owner `chassis` (`prompt_files.owner`); a prompt kept whole in a file keeps its file name as the tag, `prompt.intake:intake.axiom`; a skill's procedure is named by its address, `prompt.skill.<name>`, so the store's `skill:<name>` and BASE-059's `logic.skill.<name>` become one name; a prompt registered from another file (`prompt-registry.json`, MCP-031 as amended 2026-10-06) takes `prompt.<owner>:<name>`.
- Why: A prompt that has an address can be named in a ticket, a workflow, an override and a review the same way any other part of the system is named. The same form as prompt joins and refs (CTX-081) means one way of reading everywhere.
- How it shows: `metaform prompts review` lists `prompt.dispatch:system`. `metaform prompt prompt.dispatch:system` shows its versions. `metaform agents role name=worker` lists `prompt.dispatch:work`.
- Build: Ticket code.engine.workflow#15 (its note of 2026-10-15 records this). The key is formed in `src/metaform/prompt_files.py:164` (`f'{owner(folder)}:{name}'`, in `served`, uncommitted) and in `served_text` (`:185-192`); the Agents module's `ROLES` in `src/metaform/modules/agents/__init__.py:49-97` (untracked); `src/metaform/prompt_review.py` `catalog()`; and the prompt store, `src/metaform/data/prompts.py`. Renaming means renaming each `prompts.name` row in place, which keeps `prompt_id` and every version, on a copy of `prompts.sqlite3` first.
- Acceptance: (1) After the rename, a prompt with an edit saved under `dispatch:work` is served under `prompt.dispatch:work` with the edit as its newest version and the same version ids. (2) A layer linked in `prompt_uses` to a version before the rename is still listed by `layers_by_prompt_version`. (3) `metaform prompts review` lists no module prompt under the old form. (4) The Agents module's role reads name every prompt in the new form, and each resolves.
- Relates to: amends MCP-031 (its amendment of 2026-10-06: the review's names are these addresses); amends STORE-044 (a prompt's `name` is its address); amends BASE-059 (a skill's store name and address are one, `prompt.skill.<name>`); CTX-080, CTX-081, CTX-083.
- Status: confirmed, 2026-10-15, in conversation with the owner, for `prompt.<module>:<tag>`. The names for chassis prompts, whole-file prompts, skills and registered prompts are recommended. Not built.

### CTX-083 The Agents module tracks each role's prompts by their addresses, served through the prompt store, so an override is what agents are sent

- Requirement: The Agents module keeps, for each role an agent Metaform starts runs as, the prompts it is sent in order and when, by their `prompt.<module>:<tag>` addresses. Every one of those prompts is served through the prompt store, so a person's saved override is the text agents receive from their next turn.
- What this means:
  - The roles are the code's: `intake`, `system`, `sentinel`, `talk`, `prep`, `worker` (`settings.AGENT_ROLES`). The code is the reference; BASE-054's six roles are a different set and are reconciled separately.
  - The module does not hold the prompts. Each one stays in its module's `prompts.xml` and that module still sends it, through `prompt_files.served`, which serves the store's newest version: the shipped text, or an edit saved in its place.
  - `agents override` saves an edit, and the shipped text becomes version 1 first so the edit has a parent. `agents drop` makes the shipped text the newest version again. Both carry a caution, and an agent of a role held back by `roles_without_authority` is refused. An edit that is not well formed is not sent; the shipped text is sent instead and the role shows why.
  - `agents sent` says which role a session ran as and which prompt versions each of its turns carried, recorded from dispatch's `prompt.sent` event.
  - The Canonical Intake is never stored or overridden (STORE-044). Its role shows it as fixed.
- Why: A person who wants to change how an agent behaves has to be able to find the prompt that agent is sent, change it in one place, and know the change reached the agent. Naming prompts by address, and serving every one through the versioned store, makes the override the text actually sent, and keeps a record of which version each turn carried.
- How it shows: `metaform agents role name=worker` lists `prompt.dispatch:work` with its revision and origin. `metaform agents override name=prompt.dispatch:work text=... --confirm` makes the next turn of every worker carry the edit, and `metaform agents sent session=<id>` shows the new version number on that turn.
- Build: Built 2026-10-15, ticket 3a1306bd, not yet committed: `src/metaform/modules/agents/` (untracked): `ROLES` and `ANY` at `__init__.py:49-97`, verbs `roles`, `role`, `sent`, `override`, `drop` at `:466-480`, the `prompt.sent` subscription at `:482`, and the table `sent`. `prompt_files.served` at `src/metaform/prompt_files.py:158-182` and `served_text` at `:185-192` (uncommitted). The prompt store changes are in `src/metaform/data/prompts.py` (uncommitted). Still to build: the names in `ROLES` and every lookup take the `prompt.<module>:<tag>` form (CTX-082), ticket code.engine.workflow#15.
- Acceptance: Built and protected by `src/metaform/modules/agents/tests/test_agents.py`: `test_roles_lists_the_code_s_six_roles_each_with_the_prompts_it_is_sent`, `test_role_shows_each_prompt_with_its_text_and_the_version_the_store_sends`, `test_a_renamed_prompt_element_makes_show_report_the_broken_name`, `test_an_override_is_sent_in_place_of_the_shipped_text_and_drop_goes_back`, `test_override_refuses_an_edit_that_is_not_well_formed_and_an_agent_held_back`, `test_drop_refuses_a_prompt_with_no_edit`, `test_a_shipped_change_behind_an_override_is_shown_on_the_role`, `test_sent_reads_the_role_and_the_versions_each_turn_of_a_session_carried`, `test_the_canonical_intake_is_shown_as_shipped_and_never_overridden`. To add with the rename: each role's prompts read in the `prompt.<module>:<tag>` form, and an override saved under that name is the text the next turn carries.
- Relates to: BASE-052, BASE-054 (whose roles differ from the code's), STORE-044, MCP-031, CTX-082.
- Status: confirmed and built, 2026-10-15 (uncommitted), for the tracking and the override served through the prompt store. Confirmed, 2026-10-15, in conversation with the owner, for the addresses; that part is not built.

### CTX-084 {this} in a prompt is the node being worked on, read with its stored field names

- Requirement: In any prompt Metaform sends, `{this}` is the node the agent is working on, and `{this.<field>}` is filled with that node's stored field, by the field's stored name.
- What this means:
  - The node is an element or a join, decided by where the agent works (the pushed delivery records, decision 16, CTX-042) or, for a ticket, its node.
  - Fields are named as the store names them. For an element: `this.address`, `this.name`, `this.name_length`, `this.short_name`, `this.role`, `this.parent`, `this.layer`. For a join: `this.purpose`, `this.ef`, `this.ifd`. What modules and layers hold there is read as MAP-057 names it: `this.memories`, `this.work`, `this.messages`, `this.items`, `this.properties`, `this.context`, `this.note` (the person's note, CTX-089). Refs read flat, CTX-085.
  - Field names are the stored ones and only those. A join reads per MAP-020: purpose, ef, ifd and the elements it holds. MAP-057's `verb`, `non_goal` and `name` on joins are gone, since MAP-020 removed them. `this` is read, never assigned (MAP-057).
  - This is MAP-057's `this`, extended from prompt joins to every prompt Metaform sends that names it. In a prompt, the fill place is the braced form, `{this.address}`, beside MCP-031's empty-element places such as `<work_id/>`. The memory prompt of decision 12 (CTX-026) is the first prompt to use it.
  - Only `{this}`, `{this.<name>}` and paths below it, plus the named fills a prompt is defined with (such as `{project}`), are filled. Any other braced text is left as written, so Axiom's own `{Variable}` names are untouched.
  - Recommended: a `{this.<name>}` the node lacks is filled with nothing, and the sender notes it on stderr, the way `served` reports an edit that is not well formed. The prompt is still sent. With no node, a prompt supplies the line it uses in place of the one naming `{this}`, as decision 12 does for the memory prompt's line 2.
  - Open: what `this.purpose` reads on an element, which stores no purpose (MAP-015).
- Why: A prompt written once has to fit each node it is used at. Naming the node's values by the store's own field names means the person writing a prompt and the code filling it use one vocabulary, and the agent reads plain values, not ids (MAP-057). The paper's section 8.1 performs referential interpretation before execution: the node's name and address are filled in before the agent starts, not left for it to look up. Everything a prompt says about the node comes from one place, read the same way a subroutine reads it. An agent already reads Python's attribute syntax without instruction, so a prompt adapts to the node it is filled at without being rewritten for each one.
- How it shows: Sent to a worker on `code.alarm.audible`, the memory prompt's line 2 reads "This is code.alarm.audible (audible alarm) or any other address you work on for this session."
- Build: Not built for sent prompts: `prompt_files.rendered` fills only empty elements. MAP-057's `this` is built for prompt joins run by the workflow executor, in `src/metaform/modules/workflow/element.py:112-147` (`element_value`). A join's `purpose`, `ef` and `ifd` are not top-level fields there; they are read through `this.require` and `this.provides`. The fill needs a reader of the node's fields that `served` can call. No ticket on the 2026-10-15 list builds it; the memory prompt's ticket (code.store.memory#2 or the pushed delivery tickets) has to take it, or a new ticket does. The skill library teaches MAP-057's form (src/metaform/skills/resources/prompts.xml:226-256) and follows any change.
- Acceptance: (1) A prompt holding `{this.address}` and `{this.name}`, sent for a ticket on `code.alarm.audible`, carries that element's address and name. (2) For a ticket on a join, `{this.purpose}` carries that join's purpose. (3) `{Element_A}` in the same prompt is sent unchanged. (4) `{this.nonexistent}` sends the prompt with nothing in that place and writes a line to stderr.
- Relates to: amends MAP-057 (`this` is the node worked on in any prompt Metaform sends, an element or a join; a join's `purpose`, `ef` and `ifd` are its top-level fields; refs also read flat, CTX-085); amends MCP-031 (the braced `{this...}` form is a fill place alongside empty elements); MAP-015, MAP-020, MAP-048, CTX-027, CTX-085, CTX-087, the memory records of decision 12 (CTX-026), the pushed delivery records of decision 16 (CTX-042).
- Status: confirmed, 2026-10-15, in conversation with the owner. The handling of a missing field and of no node is recommended. What `this.purpose` reads on an element is open. Not built for sent prompts.

### CTX-085 Refs read flat on {this}, by their names

- Requirement: A ref on the node is read by its name directly on `this`: `{this.main}` is the ref named `main`.
- What this means:
  - Recommended: a ref's name is its `ref_id`, unique in the project (the ref records of decisions 20 and 21, CTX-065 and CTX-066). Open, for the owner: decisions 21 and 22 meet at `main`: is `main` a ref_id (then not unique per project), or a name the node gives its main ref, distinct from the ref_id? Read on `this`, a ref at the node gives its value, a path for a code ref. `this.main` is the node's main artifact ref (CTX-086).
  - A ref name that holds periods, as a code qualified name does, reads as a subscript, `this["metaform.modules.dispatch.runner.link"]`, by MAP-057's rule for keys that hold dots. This is recommended.
  - At a join, `this.<ref name>` reads the join's own refs.
  - A flat read only reaches a ref whose name is not a reserved field name (CTX-087), so `this.name` is always the node's name and never a ref.
  - MAP-057's `this.refs["<key>"]` still reads the older key-and-value refs (MAP-021) by key.
- Why: A prompt that reads `this.main` is short, and reads like code an agent already knows. A reserved field set keeps the flat read unambiguous. A prompt that has to know a ref's key and position (`this.refs["path"][0]`) breaks when the order or the key changes. A named ref says what it is, and a prompt can rely on it by that name.
- How it shows: A worker prompt holding "Open {this.main} first." is sent as "Open src/metaform/modules/dispatch/runner.py first." on the runner's element.
- Build: Not built. It depends on ref records with names (code.graph.knowledge#c). The read joins the node's fields in `element_value` (`src/metaform/modules/workflow/element.py:112`) and the prompt fill of CTX-084. Today `this.refs` groups the sources layer's refs by key (src/metaform/modules/workflow/element.py:95-99, :130).
- Acceptance: (1) A ref named `main` at an element is read by `{this.main}` and by `this.main` in a prompt join. (2) A ref named anything not reserved is read flat by its name. (3) `this.refs["path"]` still reads the path refs. (4) A name with periods reads by subscript. (5) In a prompt join, a ref name not on the node raises, and `.get(name)` gives None.
- Relates to: amends MAP-057 (refs read flat by name, besides `this.refs["<key>"]`); MAP-021; CTX-066, CTX-084, CTX-086, CTX-087, the ref records of decisions 20 and 21 (CTX-065, CTX-066).
- Status: confirmed, 2026-10-15, in conversation with the owner. Not built.

### CTX-086 The intake names each element's main artifact ref main

- Requirement: When the intake records an element's refs, the ref to the element's main artifact is named `main`, so that every prompt can rely on `this.main`.
- What this means:
  - `main` is the artifact that most realizes the element: the file, document or medium a person would open first.
  - It is the one ref name the intake must use. Its other refs are named as CTX-066 says.
  - It is a convention the intake is told to follow, not a check. An element recorded with no `main` is stored as given, and Metaform never refuses it (CTX-091). Which artifact is main is the model's choice.
  - A node with no artifact of its own has no `main`. CQUs and anything under `upstream` or `downstream` are links that hold no element of the project (MAP-014).
  - A prompt that reads `{this.main}` at a node without one gets CTX-084's handling of a missing field.
- Why: Prompts written once for every node need one name they can count on for "the thing itself". Making it a convention in the intake, not a gate, keeps the choice of artifact with the model (decision 25).
- How it shows: After an intake, `metaform map where code.dispatcher.runner` lists a ref `main` with the runner's main file. A prompt reading `{this.main}` there is filled with it.
- Build: Not built. The intake's text gives refs only by key (`{Ref_Member} := { key := path, ... }`, `src/metaform/modules/intake/resources/intake.axiom:15`). The intake's `refs` field asks only for key and value pairs (src/metaform/modules/intake/resources/prompts.xml:68 for elements, :79 for purpose records), and the intake procedure sets `key = 'path'` (src/metaform/modules/intake/resources/intake.xml:131). The Canonical Intake is the owner's text, served as shipped and never edited by an agent (BASE-039, STORE-044). So the instruction goes in either as owner-approved wording in the intake, or through the intake module naming the first path ref given with an element `main` when it records it. That choice is the owner's, open question 18 of this section. It goes with the ref records, code.graph.knowledge#c. Open, for the owner: decisions 21 and 22 meet at `main`: is `main` a ref_id (then not unique per project), or a name the node gives its main ref, distinct from the ref_id? (CTX-066)
- Acceptance: (1) An intake that records an element with refs leaves a ref named `main` at it. (2) An element recorded with no refs is stored with no `main` and no error. (3) An intake that names a second `main` at the same element gets the uniqueness refusal.
- Relates to: MAP-014, MAP-021, MAP-040, BASE-039, STORE-044, CTX-066, CTX-084, CTX-085, CTX-091, the ref records of decisions 20 and 21 (CTX-065, CTX-066).
- Status: confirmed, 2026-10-15, in conversation with the owner. How the intake is told is open, and so is whether `main` is a ref_id or a name distinct from it. Not built.

### CTX-087 Field names that are nouns are reserved and cannot be ref names

- Requirement: The field names `name`, `address`, `role`, `parent`, `layer`, `note`, `work`, `messages`, `memories`, `context`, `items`, `properties` and `purpose` are reserved on `this` and are never ref names.
- What this means:
  - A flat read on `this` (CTX-085) must always give the field when a reserved name is used. A ref given a reserved name is not stored under it. How the call answers (refused with the next step, or stored under another name with a notice) is set by the ref records' rule for unique names (CTX-066). A refusal writes nothing and returns, as BASE-044's operation that cannot apply, a notice naming the reserved field and the next step, with `is_error` false and exit 0. This is a mechanic of addressing, not a judgement of the name (CTX-091).
  - Open, for the owner: whether the other names `this` reads are reserved too. Those are `ef`, `ifd`, `name_length`, `short_name`, `require`, `provides` and `refs`, the last for as long as `this.refs` exists.
- Why: If a ref could be named `name`, `{this.name}` would mean two things, and every prompt using it would break at that node.
- How it shows: `map knowledge add-item` that gives a ref the name `purpose` does not store a ref named `purpose`; the result names the reserved list and the next step. Linking a ref named `address` is refused, naming `this.address`.
- Build: Not built. It goes with ref naming in code.graph.knowledge#c, with CTX-065 and CTX-066. The list lives in one constant that the ref writer and the `this` reader both import.
- Acceptance: (1) Each reserved name given as a ref name is not stored under that name, and the result names the next step. (2) A guard test finds the same list in the ref writer and in the `this` reader. (3) `main` and `schema` are accepted.
- Relates to: MAP-057, BASE-044, CTX-066, CTX-084, CTX-085, CTX-091, the ref records of decisions 20 and 21 (CTX-065, CTX-066).
- Status: confirmed, 2026-10-15, in conversation with the owner, for the thirteen names. Whether the other field names are reserved is open. Not built.

### CTX-088 Elements and joins of the base hold no note, and every note already there moves word for word to the critic layer

- Requirement: No element or join in a base has a note field. Every note that was in a base is moved, word for word, to an item of the critic layer at the same element or join.
- What this means:
  - The base holds RE, PE, OP and EF and nothing else (decision 1's records, CTX-001; the owner's rule of 2026-10-12). Agents used the note the way they now use memories, which made a dandelion of spokes at every node.
  - The field is deleted from the code, not switched off: the column, the edit path, the views that carry it, and the intake's acceptance of it.
  - Every note already in a base, in every metaform of every registered project, becomes one item of the `critic` layer at the same element or join, word for word, with nothing dropped (records stay exact). The move runs on a copy first, and a query then shows no base holds a note.
  - A note given to the intake with an element or purpose record is kept as that part's critic item, and the result says so. It is not refused (STORE-026).
  - The owner's correction on code.graph.knowledge#d, 2026-10-15, adds that no note field remains anywhere except the person's (CTX-089). An element or join that a knowledge layer added carries none either, and one it holds moves the same way.
- Why: A note field on the map invites agents to write findings into the map itself, where they pile up and bury the RE, OP and EF the map exists to show. Findings belong in memory or knowledge layers, where they are layered, hideable and addressed (paper 7.1, 7.2).
- How it shows: `metaform map where <address>` shows no note on the element or its joins. A note sent to `intake element ... note=...` is listed as a critic item at that element, with a notice. An edit of a base element with `note=` is not applied, and the notice names the critic layer call.
- Build: Ticket code.graph.knowledge#d (0e978fb9), taken 2026-10-15 by a Claude session and in progress. Already built and committed: `base_only` in `src/metaform/data/writes.py:333-345`, applied at `:418` and `src/metaform/data/layering.py:333`, refuses a note on a base element or join with a notice naming the critic layer; the intake keeps a note as the critic item (`src/metaform/modules/intake/__init__.py:134-137`, `:458-476`); `add_element` and `add_join` take no note (`src/metaform/data/store.py:224-239`). The notes already in bases were moved on 2026-10-15 (MAP-046's amendment of that date): 9 in the metaform base app-internal-refactor and 25 in the mgm base main, each word for word as a `critic` item, with each base element or join refined to hold none; no other registered base held one. Still to build: delete `note` from `EDITABLE` and `TEXT_COLUMNS` in `src/metaform/data/rows.py:27-32` and from `src/metaform/data/views.py:51,81`, with a layout upgrade that drops the column after carrying any note still found to the critic layer (STORE-029).
- Acceptance: (1) `src/metaform/modules/intake/tests/test_intake.py::test_notes_missing_and_join_refs_are_kept_as_the_intake_records_them` (built: the note is the critic item, and the edit is refused with the critic notice). (2) To add: a copy of a store whose base holds notes is upgraded, each note reads back word for word as the critic item at its element or join, and the base has no note column. (3) To add: a grep guard finds no `note` among the base's element or join fields.
- Relates to: MAP-020 (a join holds no field beyond its shape; the column outlived that record and goes), MAP-040, STORE-009, STORE-010, STORE-026, STORE-029, LAYER-025, MAP-046 (its amendment of 2026-10-15), CTX-001, CTX-089, CTX-090.
- Status: confirmed, 2026-10-15, in conversation with the owner. Built in part (refusal and intake routing). The existing notes were moved 2026-10-15; the column's deletion is not built.

### CTX-089 The person's note is the one note at a node, and only the person writes it

- Requirement: Each node has one note, at most 2048 characters, written by the person alone from the web page. No agent, MCP tool or CLI verb writes or edits it.
- What this means: VIEW-034 stands as written for storage, size and the Notes window. The `memory note` verb reads the note on every surface and writes only on the surface `web`. On the command line or over MCP a `text` is refused and nothing is written. No other note field exists at a node (CTX-088).
- Why: The note is how the person speaks to everyone working at a node. If agents could write it, it would become another dandelion and the person's word would be lost among theirs.
- How it shows: Right-click on a node, then Notes, writes its note. `metaform memory note element:code.alarm.audible text=...` from the command line or over MCP is refused, and nothing changes.
- Build: Built: the `notes` table and `note` verb in `src/metaform/modules/memory/__init__.py:974-1001`, which refuses text off the web surface at `:982-983`; the verb is declared at `:1236`; the page's `#notes` window and `POST /api/note` (VIEW-034). The check that nothing else writes the `notes` table belongs to code.graph.knowledge#d.
- Acceptance: `src/metaform/modules/memory/tests/test_memory.py::test_a_node_holds_one_note_of_at_most_2048_characters_that_only_the_person_writes` (built). To add: a guard test that the only writer of the `notes` table is the `note` verb on the surface `web` (and the rekey and upgrade paths, which carry notes over).
- Relates to: VIEW-034, VIEW-011, VIEW-030, STORE-020, CTX-088, CTX-090.
- Status: confirmed and built, 2026-10-15; the owner's correction on code.graph.knowledge#d keeps the person's note, restricted as VIEW-034 has it.

### CTX-090 The person's note is pushed whole to an agent working at its node, once per session

- Requirement: When an agent works at a node that has the person's note, the whole note is pushed to it once per session, with the memories and knowledge that apply there. It goes again only when the agent works at the node after a compaction.
- What this means:
  - The note is how a person instructs agents at one node without editing AGENTS.md or another instruction file. So it is on the show-once list of pushed delivery (decisions 14 and 15).
  - It is pushed whole: never cut to fit, never replaced by a count or a reference. Recommended: `node_summary_bytes` limits what else is pushed with it, and not the note.
  - Open, for the owner: whether the person's note is inherited toward the leaves as other properties are (decisions 2, 3), or is pushed only at its own node.
  - Until pushed delivery is built, the ticket's first message and the node read carry it whole whenever it is set (the owner's correction on code.graph.knowledge#d).
- Why: A note for agents that agents only see as a count is a note they never read. Pushing it whole, at the node it is about, puts the person's instruction where the work is, once, without costing context on every turn (paper 7.1: memory and instruction have a functional location).
- How it shows: The person writes "Keep this API stable; the mobile app pins it." on `code.service.query`. The first time a worker's session touches that node, the push carries those words, and later calls there in the same session do not repeat them.
- Build: The interim is built (code.graph.knowledge#d, uncommitted): dispatch `handoff_parts` (src/metaform/modules/dispatch/__init__.py:3020-3023) carries the note whole as `the person's note here: <text>`, read through memory's `person_note` (src/metaform/modules/memory/__init__.py:959), provided as `memory.note`; the node read carries it under `memory`. Protected by test_dispatch.py::test_the_handoff_carries_the_persons_note_at_the_node_whole_and_nothing_when_none_is_set. The counts still count it: `node_count` (`src/metaform/modules/memory/__init__.py:1036`, the note counted at `:1050`), with the counts legend naming `memory note` (`note_counts`, `modules/memory/resources/prompts.xml:18`); `node_read` is at `:1002-1035`. The once-per-session push is not built. Pushed delivery is code.adapter.context#4 and #5, code.graph.knowledge#e, code.bus.event.relay#4 and code.dispatcher.agent#40-#42.
- Acceptance: (1) A session that first works at a node with a note receives the note's full text. (2) A second call naming that node in the same session does not carry it. (3) After a `compaction_update` with status `completed`, the next work at the node carries it again. (4) A 2048-character note arrives whole when `node_summary_bytes` is smaller.
- Relates to: amends VIEW-034 (its Why of 2026-10-04 says the note is not for the AI; it now is the person's instruction to agents at that node, and agents receive it whole); amends MAP-048 (its acceptance that a ticket read carries none of the note's text: the note is carried whole); amends MCP-039 (the note is no longer only a count); VIEW-034 (its amendment of 2026-10-15); CTX-089, the pushed delivery records of decisions 14 to 18 (CTX-040 to CTX-050).
- Status: confirmed, 2026-10-15, in conversation with the owner. The budget reading is recommended. Whether the note is inherited toward the leaves is open. Built for the interim (whole in the hand-off and the node read); the once-per-session push is not built.

### CTX-091 Metaform never gates or judges inference; it enforces mechanics only

- Requirement: How an intake names nodes, and how an agent names refs, layers, memories and prompts, is the model's choice. Metaform refuses or redirects only for mechanics: linking a file before writing it, the read-only ignore list, once-only delivery, unique names, the reserved field names, a title and why on a new memory, question or ticket resolution (MCP-037, BASE-040), a locked memory (CTX-023), the person-only note (CTX-089), and the authority of a held-back role (CTX-083).
- What this means:
  - No write is refused or graded for its wording, its typology, the depth of its address or the quality of its purpose (MAP-013, STORE-026). What does not fit the shape is stored as given, or kept beside the shape (the base's notes go to the critic layer, CTX-088), with a notice.
  - The mechanics, and only these, can stop an action. A file with no exact ref is locked for writing until it is linked (decision 19). Paths in `.metaform/ignore.txt` are read-only to agents. A push is sent once per session (decisions 14 and 15). A name must be unique where it is a key (refs, layers, prompt joins on an element). A reserved field name is not a ref name (CTX-087). A new memory, question or ticket resolution carries a title and why (MCP-037, BASE-040). A locked memory is not changed by agents (CTX-023). The person's note is written only from the web page (CTX-089). An agent of a role held back by `roles_without_authority` does not override prompts (CTX-083). Each is about whether something can be addressed or delivered, never about whether the inference is good.
  - Conventions agents are asked to follow, such as `main` (CTX-086), are not checked.
  - Grading belongs in a later layer that observes, such as a critic or blind-spot layer (LAYER-014), never in the write path.
- Why: The paper, section 6: C(T) guides semantic reasoning and "does not prescribe an approval gate or a runtime check." A check that rejects inference sends agents into retry loops: an agent-built check once turned a five-minute intake into 456 minutes and $750 (STORE-026). The model is the reasoner. Metaform's job is to deliver context and keep the map addressable, not to second-guess the reasoning.
- How it shows: An intake places `media.photo.jpg`; it is stored. An agent names a layer `my layer`; it is stored with a notice that it is not in the layer name form (src/metaform/data/layering.py:114-115). An agent's write to an unlinked file is refused with the call that links it. Beyond the mechanics listed above, nothing refuses.
- Build: Built where it applies today: STORE-026's notices; `tests/test_store_reads.py::test_a_write_that_does_not_fit_is_stored_with_a_notice_and_text_is_never_judged`; `src/metaform/modules/intake/tests/test_intake.py::test_what_does_not_fit_is_stored_as_given_and_named_in_a_notice`. Link-before-write is code.dispatcher.agent#3d (built 2026-10-15, uncommitted). Every ticket of this round (code.graph.knowledge#b-#e, code.adapter.context#4-#5, code.store.memory#2, code.engine.workflow#15) adds no check beyond these mechanics.
- Acceptance: (1) The existing tests named above. (2) To add: a refusal inventory test that drives each write verb with odd but well-formed content (an off-typology address, a long name, an empty purpose, an unusual layer name, a ref with any unique proper noun) and finds every one stored, with at most a notice. The only refusals are an unlinked write, a write under ignore, a duplicate key name, a reserved name, a missing title or why, a write to a locked memory (CTX-023), a note written off the web surface, and an override by a held-back role.
- Relates to: MAP-013, MCP-037, STORE-026, LAYER-028, LAYER-014, BASE-040, BASE-044, CTX-023, CTX-083, CTX-086, CTX-087, CTX-088, CTX-089, the records of decisions 14, 15 and 19 (CTX-040 to CTX-050, CTX-060 to CTX-064).
- Status: confirmed, 2026-10-15, in conversation with the owner. Built for the store's writes; the refusal inventory test is not written.
- Amendment, 2026-10-18, the owner's decision, no ticket, landed with the change that removed the lock: the lock was withdrawn after its drawbacks were weighed, and replaced by the entry-point request (CTX-060). Linking a file before writing it and the read-only ignore list are no longer mechanics: in the requirement's list, the sentences "A file with no exact ref is locked for writing until it is linked (decision 19)" and "Paths in `.metaform/ignore.txt` are read-only to agents", How it shows's "An agent's write to an unlinked file is refused with the call that links it", the Build's "Link-before-write is code.dispatcher.agent#3d", and the acceptance's "an unlinked write, a write under ignore" among the only refusals no longer hold. Agents are asked to link entry points instead, and nothing refuses for want of a link (CTX-060).

## Amendments to other records

Each record below is amended by the records of this section, as each record's Relates to says.

- MAP-011: extended as LAYER-005 is, from properties attached to elements to every property, with the store moving the link rather than the agent judging depth; its open point about items at an address no element holds is answered: the element is created there (CTX-006, CTX-009, CTX-010).
- MAP-020: the note column that outlived its shape rule is deleted from base elements and joins (CTX-088).
- MAP-021: refs sit on an element or on a join (join items already hold most of them: 72 of 139 items). Each ref is named, and refs are the exact record that unlocks writing a file (CTX-060, CTX-065, CTX-066).
- MAP-022: in the base an encounter is a function carried by a join; outside the base everything is a property, joins an agent adds included. A property's link also moves by itself to the common prefix (CTX-004, CTX-009). Its second acceptance line holds for joins in the base only (CTX-002, CTX-004).
- MAP-022, LAYER-003, LAYER-005 and STORE-039: 'a property attaches only to an element, never to a join' and STORE-039's 'a property sent to a join is stored as given, orphaned' (and that acceptance line) no longer hold for the properties of CTX-004; a property at a join is linked at its receiver's address (CTX-004, CTX-008, CTX-065).
- MAP-016 Build: 'creates the element there in the writing layer' becomes 'in a new knowledge layer for that node' (CTX-011).
- MAP-040 and the intake prompts (src/metaform/modules/intake/resources/prompts.xml:68, intake.xml:131): the intake names each element's main artifact ref `main`. The wording awaits the owner (CTX-086).
- MAP-048: the hand-off is the first push and carries the content that applies at the ticket's node within the budget, not counts with none of their text; the person's note is carried whole. Its acceptance line "carries none of their text" is superseded (CTX-040, CTX-090).
- MAP-055: the amendment of 2026-10-08 reserved root `logic` becomes `prompt`; `logic.workflow.*` becomes `prompt.workflow.*` (CTX-080).
- MAP-056: a logic requirement is a prompt held in a prompt join, stored type `prompt`; calls keep the address.name form until the `:` call form is decided (CTX-080, CTX-081).
- MAP-057: says prompt, not added logic. `this` extends from added logic to every prompt Metaform sends and means the node being worked on, an element or a join. Join fields follow MAP-020 (verb, non_goal and name drop; purpose, ef and ifd are top-level fields). Refs read flat by name, such as `this.main`, and noun field names are reserved. `this.note` is the person's note. `this.memories` is the applying set, each with the address it is linked at (CTX-024, CTX-080, CTX-084, CTX-085, CTX-087).
- LAYER-001: the `unnamed-<UTC timestamp>` fallback (src/metaform/data/store.py:138-139) does not apply to a new node, which gets its own layer (CTX-011).
- LAYER-003: "functions are not transitive, so a new element with a function reaches the metaform only through its join" now holds for the base only (CTX-004); its open question 10 is answered: an address with no element is created (CTX-010). 'Those new records belong to that layer' becomes: a newly named element belongs to its own node's knowledge layer, made by the write (CTX-011).
- LAYER-004 and D73: "nothing else travels" is replaced; every property travels, memories included, along the namespace tree (CTX-004, CTX-024). Its second acceptance line ('an item at the same element is not') is superseded.
- LAYER-005: extended from properties attached to elements to every property; the agent no longer judges how deep an item belongs, because the store moves the link (CTX-006, CTX-009).
- LAYER-006: hiding a layer also hides the memories linked from it (CTX-013).
- LAYER-012: a memory at a node shows only where both the memory layer and the layer it is linked from reach (CTX-013). "Any agent may read them and add to them" is widened to create, read, update and delete by any agent, unless locked (CTX-022, CTX-023). Recommended variable "What happened in the work at this node." for memory layers made from now on, the existing layer's text left as recorded (CTX-020).
- LAYER-013 and D74: a node the active map does not hold is no longer refused for memory; the address is created (CTX-010). At a node, operations act on the memories that apply there, inherited ones included, not only entities joined to the node, and writes at a node name an entity anywhere in the graph, so the acceptance case "add_observations to an entity joined to another node stops" becomes "add_observations at a node stops only for a name the graph lacks" (CTX-022, CTX-024). 'Creating one never touches the map' gains the same exception as STORE-020 below (CTX-010). Relations at a node are those with at least one end there, and create_relations looks up an end in the whole graph (CTX-025).
- LAYER-016 Build: a knowledge item is no longer either a property or a function, and an element a layer creates is no longer kept from the namespace tree (CTX-004). Its Build's function join in the layer and its third acceptance line now read: the join is a property, returned as applying at its receiver and every address toward the leaves (CTX-004).
- LAYER-018: a new node's layer is made by the write that names the node, not only by `op=create` (CTX-011).
- LAYER-020: "Items do not travel" is replaced (CTX-004).
- LAYER-025: a finished base no longer takes add-element, add-join, add-property or add-ref; it changes only by refining (CTX-001).
- LAYER-027: the workflow-owned layer is a prompt layer (CTX-080).
- LAYER-028: its Why sentence that a language never appears in the metaform's namespace now means never in the base; a language may appear as a knowledge-layer address (CTX-003). Its 2026-10-08 amendment is settled: what a layer holds at a scope is named `<scope>@<content>` (read by src/metaform/modules/map/scoped.py; the store still flags `@` in a name, CTX-011), a ref is named `{ref_id}@{address}:{join}`, `@` reads "for" in both, and what `:` names is open (CTX-066, CTX-081, open question 25); the record's body, which still describes the single-segment name and the dot form `<layer>.<address>`, is amended to the built `@` form (CTX-066, CTX-081). A layer is never named `prompt`, and prompt joins read prompt joins (CTX-080).
- STORE-012: a ref stops being a key and value row on one version row of an item or property. It becomes its own record in the sources layer with a lasting id, who linked it, when and why, and its own versions (CTX-065, code.graph.knowledge#c).
- STORE-020: node narrowing ("the entities with a join at the node's key and the relations between them") is replaced by the applying set walked over prefixes plus relations with one end there (CTX-024, CTX-025); recommended tables version 7 with `locked_by` and `locked_at` on entities, `compatible_from` 7 (CTX-023). 'Memory writes never call add_element ... the only metaform-store write is the memory layer's creation' now holds only for nodes the map holds; a memory at a node the map does not hold creates the element there and its node's knowledge layer (CTX-010, CTX-011).
- STORE-034: a property's link now also moves by itself to the longest common prefix when the property is recorded on another branch (CTX-009).
- STORE-035: "Items, and anything attached at joins and subtypes, do not travel" is replaced; the applying and visible sets cover every property (CTX-004, CTX-006, CTX-007).
- STORE-039 and D88: how a property is recorded is settled for its link: one link to one base address (CTX-008).
- STORE-044: a prompt's stored name is its address `prompt.<module>:<tag>`, renamed in place, keeping ids and versions (CTX-082).
- BASE-040: `node_read` returns inherited memories marked with their link address (CTX-024); the unscoped "no node will show" notice for relations is dropped (CTX-025); `lock` and `unlock` verbs on the cli and web surfaces only (CTX-023). 'Never writes the map' gains the same exception as STORE-020; its acceptance 'the map is unchanged' holds for a node the map already holds (CTX-010).
- BASE-051: its 2026-10-08 amendment: `logic.workflow` becomes `prompt.workflow` (CTX-080).
- BASE-058: the ignore list was what the intake does not read. It is now also read-only to agents, whether or not a ref names the path, while reads by working agents are allowed (CTX-064).
- BASE-059: a skill's address is `prompt.skill.<name>`, one name with its prompt-store key (CTX-080, CTX-082).
- BASE-035: `Module` gains the hook that answers what applies at an Address, trunk first, beside `node_read` and `node_count`, and the read an agent works from carries that content within CTX-044's budget (CTX-040).
- MCP-029: besides the connect message, the glossary, the tools and the node summary, each agent session is sent the memory prompt whole, once, and again after a compaction (CTX-026, CTX-028). Memory's connect line, quoted in its How it shows, follows the memory/knowledge split (CTX-029).
- MCP-031: the braced `{this...}` form is a fill place beside empty elements; the review names prompts `prompt.<module>:<tag>` (CTX-082, CTX-084).
- MCP-039: the rule that an agent is told how much is held at its node and never what it holds no longer applies to the node the agent works at. That node's content is pushed once per thing per session, within `node_summary_bytes`, and what overflows is listed; the neighbours' counts stay (CTX-040, CTX-041, CTX-044). The person's note is no longer only a count; it is pushed whole once per session (CTX-090). Memory counts count the applying set at a node, inherited ones marked (CTX-024). The session record also clears on compaction (CTX-045), carries over on a resume that reopens (CTX-047), and can be named by a provisioned HTTP header (CTX-048).
- VIEW-022: the lit reach is the applying side only, and any property or the node it is linked at starts it (CTX-015). Whether its particles along the edges stay is open, with VIEW-026's wave (open question 3).
- VIEW-026: the wave's dots toward the trunk and the mesh drawn for each dot give way to lighting the nodes and edges already drawn; whether the wave remains as a pulse toward the leaves is open (CTX-015).
- VIEW-031: Lock and Unlock in the memory panel (CTX-023).
- VIEW-034: its 2026-10-04 Why ("not for the AI") is replaced: the note is the person's instruction to agents at the node, pushed whole; storage and write rules unchanged (CTX-089, CTX-090).
- D115's amendment of 2026-10-09 and the Join glossary entry in 01-map.md: logic join becomes prompt join, `type: prompt` (CTX-080).
- `prompt.memory:instructions` (memory prompts.xml:35-107): recommended, the Axiom text is replaced by the owner's memory prompt and kept as an earlier version in the prompt store (CTX-026, CTX-029).
- `prompt.memory:orient` and `prompt.dispatch:record`, `work_record`, `on_ticket_done`, `on_stopped_open`, `on_failure`: the 2026-10-11 "store what you learn" sentence gives way to wording that follows memory prompt steps 5 and 6, the wording for the owner to approve (CTX-029; related MCP-029, BASE-052).
- Not a spec record: the skill `.claude/skills/acp-client-integration/SKILL.md` (line 23) says to treat the synthetic "Compact conversation" tool call as the signal; the archived `.claude/skills/.archive/acp-client-capabilities-compaction` also says to re-push at the agent's current element on compaction. CTX-046 and CTX-045 withdraw both.
- 2026-10-15, spec reconciliation, tickets document.specification#2 and code.dispatcher.agent#47, landed at the owner's request: CTX-060 to CTX-066 brought to what is built, reflecting code.graph.knowledge#c (858e3d9), code.graph.knowledge#17, code#1e, code.dispatcher.agent#43 and #47, with the lock prompts rewritten so an agent knows how to unlock a file. Each record keeps its earlier sentences; its amendment says which no longer hold.
- 2026-10-18, the owner's decision, no ticket: the lock was withdrawn after its drawbacks were weighed, and replaced by the entry-point request (CTX-060). In MAP-021's line above, "refs are the exact record that unlocks writing a file" no longer holds: refs are the exact record that places a file. In BASE-058's line above, "It is now also read-only to agents" no longer holds: the ignore list is again what the intake does not read, and agents may write it (CTX-064, withdrawn). CTX-061, CTX-062 and CTX-064 are withdrawn; CTX-042, CTX-063, CTX-065, CTX-066 and CTX-091 are amended only in their sentences about the lock.

### CTX-092 Execution episodes preserve coherent understanding across independently recorded work

- Requirement: Related contributions can continue in one suitable ACP conversation while every work record retains its own source, outcome, candidate, caller and evidence.
- What this means: A responsible agent selects `continue_from` using the work's meaning. An episode survives session replacement. `fresh_context` reconstructs the contribution from retained intent, decisions, evidence and functional understanding when the accumulated conversation no longer helps. Independent responsibilities retain their own contexts.
- Why: New cards must not automatically discard implementation understanding or require repeated classification, planning and full handoffs.
- How it shows: Three explicitly related cards complete through one ACP session; each tool call resolves to the current assignment. Earlier results and bindings remain inspectable. A delayed child result reaches its recorded caller even after the active card changes. Historical session links still reach the selected conversation.
- Build: Orchestration stores episodes, episode membership and binding history alongside the one current session binding. Claim, delegate and call accept `continue_from` and `fresh_context`. Related continuations reuse a still-advertised runtime while honoring current explicit choices. Dispatch checks actual process ownership, session capabilities, workspace state and stops. A retained conversation receives the new operation, source references and current return route. The full prior handoff is not replayed. Workspace and candidate identities stay explicit.
- Acceptance: `orchestration/tests/test_episodes.py`, `dispatch/tests/test_episode_transport.py` and `dispatch/tests/test_episode_safety.py` cover distinct outcomes, real ACP load/continuation, fresh replacement, concurrent launch reservations, independent responsibilities, historic links and delayed returns. Actual payload/process/session counts are retained in the matched workflow measurements.
- Relates to: BASE-050, BASE-052, BASE-066, MAP-048, CTX-047, CTX-091.
- Status: Confirmed by the ACP/context rework assignment, 2026-10-23.

### CTX-093 Delivery receipts and revision notices describe observable delivery, never hidden understanding

- Requirement: Known consumers receive relevant external corrections and changed instruction references during a natural turn without unrelated broadcasts, new model calls or claims about hidden retained context.
- What this means: A delivered body, an accepted revision notice, host discovery, observed compaction and a marker response are distinct evidence. A matching marker proves only that response. An omitted marker does not establish semantic loss or justify rebuilding all context.
- Why: Longer workstreams need current knowledge without repeated reconstruction or unsolicited context floods.
- How it shows: Multiple relevant external corrections coalesce. Unrelated changes, own writes and exact rereads cause no redundant notice. Withdrawals retain identity and revision through deletion/recreation. Changed known-consumed prompts are referenced once after accepted delivery. Explicit reads still obtain complete current content.
- Build: Memory retains consumed revisions and queued references with precise snapshot revision and withdrawal identities. The optional `agent.context.changes` provider supplies `pending` and `delivered`; the role provider supplies `changes` and `delivered_changes`. Dispatch acknowledges only notices actually accepted by transport. Actual ACP compaction moves the eligibility epoch; receipt age and marker omissions do not. Effective instruction manifests retain selected, shipped, trial, fallback and pinned-source identities with native/internal state labeled unknown where unobserved.
- Acceptance: Agents authored-context, memory delivery and dispatch natural-turn regressions establish coalescing, accepted-only receipts, selected generated duties, portable definition fallback, explicit compaction, opaque resume and source changes. Native context and provider billing remain unknown unless actually reported.
- Relates to: CTX-026, CTX-040, CTX-043, CTX-045, CTX-047, CTX-091, CTX-092.
- Status: Confirmed by the ACP/context rework assignment, 2026-10-23. Supersedes age-based content expiry, marker-based semantic-loss inference and the earlier blanket no-change-notice policy.

## Open questions

1. Where does a property's link go when the two addresses it was recorded at share no segment (for example `code.x` and `data.y`)? Recommended for what counts as the same property: an item with the same value in the same layer; a property layer that is the same node. (CTX-009)
2. Does a call that names a different layer also write a new node there? Recommended: the node is held only by its own layer, so that hiding the layer hides the node everywhere. (CTX-011)
3. Does VIEW-026's wave remain as a pulse running only toward the leaves through the lit nodes, and do VIEW-022's particles along the lit edges stay? (CTX-015)
4. The replacement wording for each prompt line that sends the 2026-10-11 "store what you learn" sentence, for the owner to approve. (CTX-029)
5. Is the graph wiped on 2026-10-11 (`backup-before-delete-2026-10-11`: 111 entities, 39 relations, 25 of them crossing nodes) brought into the reprocess? For the owner. (CTX-030)
6. Does an edited note, or a memory given a new observation, count as new for once-per-session delivery? The ticket keys a note by its Address and a memory by its entity, which would not send an edit again. (CTX-041)
7. Should a push never start a turn by itself, and travel instead at the head of the next prompt something else sends? Ticket `code.dispatcher.agent#40` as written uses the turn path, which starts one. (CTX-043)
8. Do MCP-039's records of tool guidance and counts clear with a compaction? Ticket `code.dispatcher.agent#41` clears only the push records. (CTX-045)
9. The wording of the `link_call`, `work_link` and `write_ignored` prompts, drafts awaiting the owner. (CTX-060, CTX-064) Amendment, 2026-10-15: `work_link` and `link_call` rewritten at the owner's request to give the whole call with `ref=` and `why=`, and `command_unsandboxed` to name it; all three still await approval. Amendment, 2026-10-18: withdrawn with the lock; `link_call`, `write_ignored` and `command_unsandboxed` are deleted, and `work_link` is now the entry-point request (CTX-060).
10. Codex writes without asking outside read-only mode, and decision 19 requires the lock in every mode. By what method is Codex made to ask, for example read-only with its approvals answered through `dispatch_prompts`? A live check of a real Claude Code session in bypassPermissions editing an unlinked file has also not been run. (CTX-061) Amendment, 2026-10-18: withdrawn with the lock (CTX-061).
11. Shell writes and agents connected only over MCP: does a worktree whose merge refuses unlinked or ignore-listed files meet "never caught after", and may provisioned settings carry the lock for agents dispatch did not start? (CTX-062) Amendment, 2026-10-18: withdrawn with the lock (CTX-062).
12. Is the ignore-list matcher moved from dispatch into `home.py` beside `ignore_patterns`, a chassis change? (CTX-064) Amendment, 2026-10-18: withdrawn; the matcher is deleted with the ignore list's read-only rule (CTX-064).
13. Decisions 21 and 22 meet at `main`: is `main` a ref_id (then not unique per project), or a name the node gives its main ref, distinct from the ref_id? For the owner. (CTX-066, CTX-085, CTX-086)
14. Does an Axiom call also take the `:` form (`code.alarm.audible:review( ... )`), or keep MAP-056's `code.alarm.audible.review( ... )`? (CTX-081)
15. What does `this.purpose` read on an element, which stores no purpose? (CTX-084)
16. Two drafts of `{this}` differed on a field the node lacks: one had it raise, as MAP-057 has a missing key raise; the other, kept in CTX-084, fills it with nothing in a sent prompt and notes it on stderr. CTX-085 keeps raising for a missing ref name in a prompt join. Is raising kept for prompt joins run by the executor and the empty fill for sent prompts, or is one rule used for both? (CTX-084, CTX-085)
17. Do flat ref reads replace `this.refs["path"]`, as one draft had it, or does `this.refs["<key>"]` stay beside them for the older key-and-value refs, as CTX-085 has it? (CTX-085)
18. How is the intake told to name the main ref `main`: owner-approved wording in the Canonical Intake, or the intake module naming the first path ref given with an element `main` when it records it? (CTX-086)
19. Are the other names `this` reads (`ef`, `ifd`, `name_length`, `short_name`, `require`, `provides`, and `refs` for as long as it exists) reserved too? Does a ref given a reserved name get refused naming the field, or stored under another name with a notice? (CTX-087)
20. Where does a property's link go when its address, or the common prefix, has no base element, and is a node's own layer linked before it is bound? Decision 4 says one link to one base address. (CTX-008, CTX-009, CTX-011)
21. May a link be moved by hand toward the leaves or sideways, by `edit element=` or by binding a layer at a function? Decision 4 says a link never moves toward the leaves. (CTX-008, CTX-014)
22. Is the person's note inherited toward the leaves as other properties are (decisions 2, 3), or pushed only at its own node? (CTX-090)
23. An agent connected only over MCP has no ACP compaction signal, so after a compaction it would never be pushed again. How is such a session's record cleared without hooks or token heuristics (decision 17)? (CTX-045)
24. Does a `!` line in ignore.txt exempt a path from read-only, as it does in gitignore's reading? Recommended, and built: it is not read. (CTX-064) Amendment, 2026-10-18: withdrawn with the ignore list's read-only rule (CTX-064).
25. What does `:` name, the same in a ref name and a prompt's address: a join's provider's Address (so `<receiver>:<provider>`, as the scope form names a join), or a name (as CTX-082's `prompt.<module>:<tag>` uses it), or a short name for the purpose? (CTX-066, CTX-081)
26. When does `LINK_LOCK` go back on, and is it one switch for the link lock, the ignore list's read-only rule and the command sandbox together, as built, or does CTX-064's "always" keep the ignore list read-only while the link lock is off? Added 2026-10-15, document.specification#2. (CTX-060 to CTX-064; code#1e) Amendment, 2026-10-18: withdrawn; `LINK_LOCK` and `SHELL_SANDBOX` are deleted, not switched off, and agents are asked to link entry points instead (CTX-060).
