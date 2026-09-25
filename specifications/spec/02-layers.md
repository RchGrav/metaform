# 02 Layers

This section defines layers: what a layer is, how it attaches to the map, its declared properties, how select and mask decide what reaches each point, how layers are read, provenance, memory, corrections, native and latent reasoning, and the blind-spot challenge workflow.
The receiver, purpose and encounter structure itself, element identity and subtypes are in section 01; storage tables and indexes are in the storage section; the operations a module calls are in the common base section.

### LAYER-001 Everything Metaform holds is a layer

- Requirement: Every piece of knowledge Metaform holds belongs to exactly one layer, the intake's map included.
- What this means: A layer is a named body of inferred knowledge laid over the map. The intake produces a layer too: its layer is the one that creates most elements and joins. Every element, join, subtype and layer item records the layer that produced it. The core map is the selection of the intake layer. A new element proposed by a later pass lives in that pass's layer.
- Why: When everything is a layer, every piece of knowledge attaches, selects, hides and records its origin the same way. That uniformity lets modules compose, and it keeps the map from becoming a special case that every module has to handle separately.
- How it shows: Asking for an element's or join's origin always names one layer. Selecting only the intake layer shows the core map with nothing else on it.
- Build: The layer record holds: id, name, the module that owns it, variable (LAYER-002), mutable, hideable, transitive (LAYER-004), and created time; an intake layer also holds the intake result id (MAP-040). The project is the store the layer lives in (STORE-003), and hidden state is kept as in STORE-013. Every element, join and subtype record carries a layer id, never empty. Every layer item record carries a layer id, never empty. The intake writes its elements, joins and subtypes under one intake layer, created locked in the single atomic write of `intake_submit`, STORE-032, so the map appears whole or not at all. A knowledge layer is built and then locked, LAYER-018. Memory is mutable and never locked against change, LAYER-012.
- Acceptance:
  - After an intake through MCP, every stored element, join and subtype names the intake layer, and reading the intake layer returns all of them.
  - Storing an element, join, subtype or layer item without a layer is refused.
- Relates to: LAYER-002, LAYER-003, LAYER-008, MAP-040, STORE-013, STORE-014.
- Status: confirmed.

### LAYER-002 A layer carries one inferred variable

- Requirement: Each layer answers exactly one question, and every item in it is an answer to that question at the place it attaches.
- What this means: The variable is the one thing the layer infers, and for a knowledge layer it is whatever the prompt that builds the layer defines. Examples, not a closed list: a blind-spot challenge where the critic sees one, best-practice imperatives for a type, porting concerns for a move to another language, or an agent's memory. A layer never mixes two variables. Two questions make two layers.
- Why: A layer with one variable can be selected, masked, hidden, compared and trusted as a unit, because everything in it was produced the same way for the same purpose. That is what makes layers compose: a module adds its one variable without knowing about any other module, and select and mask decide which layers an agent sees together.
- How it shows: Every layer states its variable in one sentence. Reading a layer returns items that all answer that sentence.
- Build: The layer record's variable field is required text, stating the question. The operation that creates a layer refuses an empty variable.
- Acceptance: Creating a layer without a variable is refused.
- Relates to: LAYER-001, LAYER-003, LAYER-009.
- Status: confirmed.

### LAYER-003 A layer item attaches on an element, on a join, or on a new element and join

- Requirement: Each layer item attaches at one element, one join, or one subtype, or it creates a new element and join and attaches there.
- What this means: Where an item attaches is where it says something. An item about what an element is attaches at the element. An item about how a provider serves a receiver attaches at their join. An item about an absorbed part attaches at its subtype directly. When a layer's answer is something the map does not contain yet, the layer creates the element and its join, and those new records belong to that layer. The new element joins on either side, MAP-044: as a receiver it owns its join to an existing provider, and as a provider its join is held by the existing receiver that names it. Functions are not transitive, so a new element with a function or a purpose reaches the metaform only through its join. A property attaches only to an element, MAP-022. When a property belongs at a namespace prefix where the project has no element, the layer creates an element at that prefix and attaches the property to it; the namespace tree links that element to every element above it, so it needs no join.
- Why: Attaching where the knowledge applies means an agent reading any node receives exactly what was inferred about it. Allowing a layer to create its own element and join means a module can extend the map without special machinery, which is the same way the intake builds the map.
- How it shows: Reading an element returns the items attached there. Reading a join returns the items attached to that join. An element created by a later layer shows that layer as its origin.
- Build: A layer item record holds: id, layer id, attach kind (element, join or subtype), attach id, value, and the op, reason and evidence of a correction layer's rows, LAYER-011. The value is text or a structured document. Attach id refers to the stable id of the element, join or subtype, never to its address, so items follow an element through retyping. An item cannot attach to a missing target.
- Acceptance:
  - An item attached to an element stays attached after the element's type address changes.
  - An item attached at a subtype is returned by a read of that subtype and not by a read of its parent element.
- Relates to: MAP-015, MAP-031, MAP-044, LAYER-001, LAYER-008, STORE-015.
- Status: confirmed for elements, joins, subtypes, and new elements and joins, and that properties attach only to elements. Creating an element at a prefix to hold a property there, linked by the namespace tree with no join, is recommended; it replaces attaching properties at a bare type address. Whether other items may attach at a type address that no element holds is open; see open question 10.

### LAYER-004 A layer declares its properties

- Requirement: Each layer declares whether it is mutable or immutable, whether it is hideable, and whether it is transitive, and the chassis applies those rules the same way for every layer.
- What this means:
  - Mutable: its items change in place. Memory is mutable.
  - Immutable: its items never change in place. The intake layer and correction layers are immutable: the metaform, the intake map and what correction layers added, changes only through correction layers, LAYER-011. Knowledge layers are not immutable: an agent with the knowledge-layer tool can change them at any time, LAYER-018.
  - Hideable: the layer can be hidden from views and agent context while its content and history stay stored (LAYER-006).
  - Transitive: its items travel along the namespace tree as described in LAYER-005. Transitivity belongs to properties, MAP-022: a property attached to an element is transitive whatever layer holds it. Whether a layer-level transitive flag remains for other items is open, open question 12.
- Why: Declaring the behavior on the layer lets the chassis apply corrections, visibility and propagation once, uniformly. No module rebuilds these rules, and no module can apply them differently.
- How it shows: A layer's properties are listed with it. Trying to edit an item in place in the intake layer or a correction layer is refused with one next step naming the correction operation.
- Build: Three required boolean fields on the layer record, mutable, hideable and transitive, set when the layer is created. The chassis enforces them in every write and read path.
- Acceptance:
  - An in-place edit of an item in the intake layer is refused and names the correction operation.
  - A transitive item at a parent address is received at a child address; a non-transitive one is not.
- Relates to: LAYER-005, LAYER-006, LAYER-011, LAYER-013.
- Status: confirmed that layers declare these properties. Whether each property is fixed for a kind of layer or chosen by the module for each layer it creates is open.

### LAYER-005 Properties apply up toward the leaves and are visible down toward the trunk

- Requirement: A property, which is attached to an element, MAP-022, applies from that element's address to every address above it toward the leaves, and is visible, without applying, at every address below it toward the trunk.
- What this means: Orientation: the trunk is down and the leaves are up. From the address where an item is linked, it goes down to the trunk as visibility and up to the leaves as inheritance. Inheritance runs one way. A practice for `code` holds for every engine, every game engine and every FPS engine. A practice for `code.engine.game.fps` means nothing for code in general. Toward the trunk, the item is visible without applying: C++ attached at the engine and Bash attached at the installer both show at `code`, so `code` shows every medium in use in the project, yet the installer does not inherit C++ because C++ is visible at `code`. Where an item is placed is therefore strategic. Placed near the trunk, it applies to every branch after it. Placed further from the trunk, the branches beside it do not inherit it. An item that still holds with its leaf segment removed belongs lower in the tree, toward the trunk.
- Why: Every prefix of an address is a complete type with its own inference, and practice passes from parent to child. Visibility toward the trunk lets a broad question see everything in use above it without spreading a branch's specifics to its siblings.
- How it shows: Reading an address lists the properties that apply there, and separately the properties visible there from above, toward the leaves.
- Build: Transitive travel follows the namespace tree only, never the purpose graph, so it always terminates. For an address A, the applying set is the properties attached to the elements at A and at every prefix of A, after select and mask. The visible set is the properties attached to elements at any address that has A as a prefix, after select and mask. Storage and reads are STORE-039 and STORE-035. Reads return the two sets separately.
- Acceptance:
  - With C++ attached as a property to the element `code.engine` and Bash to the element `code.installer`: `code` shows both as visible and neither as applying; `code.installer` does not receive C++.
  - A property attached to the element `code` applies at the element `code.engine.game.fps`.
- Relates to: LAYER-003, LAYER-004, LAYER-007, MAP-011, MAP-022, STORE-035, STORE-039.
- Status: confirmed, including the orientation: down is toward the trunk, up is toward the leaves, and that properties attach only to elements.

### LAYER-006 Hiding removes a layer from view and keeps it stored

- Requirement: A hideable layer can be hidden and shown again; hiding removes it from every view and agent context and deletes nothing.
- What this means: Hidden knowledge stays stored with its history and provenance, and it can be shown again at any time. A port from C++ to Rust hides the C++ layers and selects the Rust layers; addresses and purposes stay unchanged.
- Why: Knowledge that no longer applies must stop steering agents without being lost, because it may apply again and because its history explains why things are the way they are.
- How it shows: After hiding a layer, no read, view or context assembled for an agent contains its items. Showing it restores them unchanged.
- Build: The layer's hidden state, stored as in STORE-013. Every read path and every context assembly path filters hidden layers out. Hiding a layer that is not hideable is refused with one next step. Correction layers are never hideable, LAYER-011.
- Acceptance: A hidden layer's items appear in no element read, join read, layer-at-node read or MCP read, and reappear unchanged when it is shown.
- Relates to: LAYER-004, LAYER-007, STORE-013.
- Status: confirmed for hiding a layer. Hiding is of whole layers only, per D20's recommendation. Whether hiding a layer also hides the layers built from it is open.

### LAYER-007 Select and mask decide which layers reach each address

- Requirement: At each namespace address, the effective selection is (incoming & mask) | select, computed from trunk to leaf, and it applies on every path by which knowledge reaches an agent.
- What this means: Selection is a set of layers. The layers toggled on for the working context supply the starting selection at the trunk, LAYER-019. At each address, a mask can block layers coming up from the trunk, and a select can turn layers on from that address downward. An address with no select and no mask passes its incoming selection through unchanged. A mask on `code.engine` can block porting notes for everything under it, and `code.engine.renderer` can select them again for itself. The same selection governs direct element reads, property and provider context, workflow context and MCP reads. A layer excluded at an address cannot reach an agent there through a property or provider path. Correction layers take no part in select and mask: they are always applied, in order, LAYER-011.
- Why: Select and mask let one map serve many jobs, each seeing exactly the knowledge meant for it at each place, without copying knowledge or building a separate map per job. Applying the same rule on every path is what makes the selection trustworthy: an excluded layer that leaks in through a side path defeats it.
- How it shows: Two jobs with different starting selections read the same element and receive different layers. Selecting a layer at a child address makes it appear there and above it toward the leaves, and nowhere else.
- Build:
  - A selection entry holds: project, address, layer id, kind (select or mask). A mask entry names a layer blocked at that address; the mask applied is all layers except those named.
  - Resolution at address A: start with the starting selection, the layers toggled on, LAYER-019; for each prefix of A from the trunk to A itself, set selection to (selection minus the layers masked there) plus the layers selected there.
  - Resolution follows the namespace tree only, never the purpose graph.
  - An element's effective selection is the effective selection at its address. Every context assembly path calls this one resolution.
  - The starting selection is the folder's `--layers` setting, CLI-033; when it is unset, every finished layer that is not hidden starts selected.
  - Selection data that cannot be applied faithfully, a select or mask row whose layer is hidden or still building, is kept and reported as unresolved by the resolution read, STORE-035, never replaced by a broad default.
- Acceptance:
  - With layer L masked at `code.engine` and selected at `code.engine.renderer`: L reaches `code.engine.renderer`, and does not reach `code.engine` or `code.engine.physics`.
  - A layer masked at an element's address is absent from context assembled through a join whose provider carries that layer.
- Relates to: LAYER-005, LAYER-008, LAYER-009, STORE-019, MCP-003.
- Status: confirmed. Whether a join has its own select and mask, or uses its receiver's, is open; using the receiver's is recommended because the receiver owns the join.

### LAYER-008 Layers are read directly

- Requirement: A whole layer, or every layer at one element, join or subtype, is one direct indexed read.
- What this means: The store is a multilayer graph: one set of nodes with many layers over it. Two reads are basic. By layer: everything one layer holds. By node: every layer's items at one element, join or subtype. A node read comes in two forms: raw, with every stored layer; and in context, filtered by the effective selection and hidden state.
- Why: Agents navigate by meaning, one question at a time. Each question must be answered by going straight to the answer, so the structure does the orienting and the agent keeps its inference for the task.
- How it shows: Reading a layer or a node returns at once regardless of how large the project is. No read scans every record to find one.
- Build: Indexes on layer item by layer id, and by attach kind and attach id; on element, join and subtype by layer id. The by-node read in context applies LAYER-007 and LAYER-006.
- Acceptance: The raw read and the in-context read of the same node differ exactly by the masked and hidden layers.
- Relates to: LAYER-007, STORE-005, STORE-025.
- Status: confirmed.

### LAYER-009 Comparing is a view, not a stored record

- Requirement: Comparing two layers means selecting both; the comparison itself is never stored.
- What this means: Two perspectives on the same nodes, such as a blind critic's blind-spot layer and a sighted critic's blind-spot layer, are two layers. Selecting both at a node puts them next to each other. Where they disagree is found by the view reading both layers, not by a record holding both answers.
- Why: Each layer stays one variable with one provenance. Storing a comparison would mix two perspectives into one record and give it no single origin.
- How it shows: Selecting two layers at a node shows both sets of items, each labeled with its layer and provenance.
- Build: No comparison record exists. A view takes a list of layer ids and returns, per node, the items of each layer grouped by layer.
- Acceptance: None beyond LAYER-008; the rule is enforced by the absence of a comparison record.
- Relates to: LAYER-002, LAYER-014, LAYER-015.
- Status: confirmed.

### LAYER-010 Provenance is one record per layer

- Requirement: Every layer except memory has exactly one provenance record, stating how the layer was created: the module and the workflow within it, the prompt, the model, the role, and whether the producer was blinded.
- What this means: Everything in a layer was produced the same way, by one producer following one prompt in one role, so one record describes the origin of every item in it. Nothing is recorded per item, per change or per read. Blinded means the producer saw the map and not the artifact.
- Why: Provenance tracks what a feature actually uses and nothing more. Knowing how a layer was made, by which perspective under which role, is what lets layers be trusted, compared and reproduced. Per-item and per-read records turn provenance into bloat, and bloat defeats a system whose purpose is to give agents only what matters.
- How it shows: Asking for any layer's origin returns one record. Two critics' blind-spot layers over the same metaform show two records, for example one blinded and one sighted, each with its role.
- Build: The provenance record holds: layer id (unique), module, workflow, prompt (the full text as delivered), model, role, blinded. It is written when the layer is created, by the operation that creates it, and never changes: it is fixed as written through building and locking. A layer other than memory cannot be created without it.
- Acceptance:
  - Creating a non-memory layer without provenance is refused.
  - Writing a thousand items to a layer leaves exactly one provenance record for it.
- Relates to: LAYER-012, LAYER-014, LAYER-015, STORE-016.
- Status: confirmed. What the record holds for a layer written directly by a person, with no model or prompt, is open. Whether a second run adding items to an existing layer is the same layer or a new layer is open.

### LAYER-011 Correction layers are chronological, stacked, and the only way to change the metaform

- Requirement: Correction layers are applied in the order they were made, stacked on top of the intake map, and they are the only thing that can remove, relocate, or permanently add something to the metaform.
- What this means: The metaform an agent reads is always the intake map with every correction layer applied in order. A correction layer is a knowledge layer whose content is corrections: new versions of elements, joins, subtypes and properties, removals, relocations, and permanent additions. Relocating an element takes everything attached to it along, because at that point what is attached is most likely a property. An element is only a namespace address, so removing it does not drop what is attached: those things are orphaned, kept and not shown, and if an element is later put back at the same address, whatever was attached there shows again, because its element is back. Things attached to its joins cannot follow: relocation makes those joins disappear, and a join at the new place is a different join. Element records are only a namespace address with no data of their own, and things are linked to them, so an element's attachments follow it; a join is the face between a specific receiver and provider, so it does not survive a move. Knowledge layers extend the metaform only while they are toggled on, and plans stay in their layers; only a correction layer changes the metaform itself. Correction layers always beat knowledge layers: they sit underneath. The metaform is the intake map with the correction stack applied, and knowledge layers sit on top of that result. A correction layer never changes a knowledge layer's things. When a correction removes or relocates something so that a knowledge item, or a knowledge layer's join, has nothing left to attach to, that item is orphaned: it stays stored, but no read in context shows it, because there is nothing for it to be attached to. Items attached to a relocated element still follow it; items on a join that disappears are orphaned. Correction layers cannot be toggled: they are not part of layer select or mask, `--layers`, or hiding. A correction layer in the middle of the stack cannot be deleted. To remove one, walk the stack backwards, peeling layers off the top one at a time, and rebuild the ones above it; or put another correction layer on top. Each correction layer carries its one provenance record like any layer. Knowledge built on a thing a correction layer changed is re-examined and never rewritten: layers that depend on it are marked for re-examination, and their contents stay as they were until someone re-examines them.
- Why: The metaform is the shared foundation, so every change to it must be explicit, ordered and traceable, and every agent must stand on the same foundation. A chronological stack gives one answer to what the metaform is, and each change keeps the provenance of the layer that made it. Toggling corrections would give agents different foundations, and deleting one from the middle would change what every later correction was applied to; peeling from the top keeps every remaining layer applied to exactly what it was built against. Rewriting dependents silently would put inference into them that nobody performed.
- How it shows: The correction stack lists its layers in order. After a correction layer that retypes an element is finished, every read shows the new address, and the element's history shows the intake's version and each correction layer's version in order. Peeling a correction layer that is not on top is refused, naming the top layer. Layers built on the corrected thing show that they need re-examination.
- Build: The stack, applying a correction layer when it is finished, peeling the top layer, and the history read are STORE-017; what a correction may change and what a removal requires are STORE-034; the dependency marking and how it is cleared are STORE-036. A correction layer is built like any knowledge layer, LAYER-018: freely edited by its builder until locked, and applied only when locked.
- Acceptance:
  - Two correction layers change the same element; reads show the later one's version, and history shows the intake's version, then each correction layer's in stack order.
  - Peeling the lower of two correction layers is refused and changes nothing; peeling the top one restores the metaform as it was before that layer was finished.
  - Selecting, masking, toggling or hiding a correction layer is refused.
  - A correction layer changes no item in any other layer.
  - A correction that removes an element orphans a knowledge item attached to it: the item is absent from every read in context, and a raw read returns it marked orphaned.
  - A later correction that puts an element back at the same address shows that item again in context, with no row of its layer rewritten.
- Relates to: LAYER-004, LAYER-006, LAYER-007, LAYER-010, LAYER-018, LAYER-019, MAP-015, STORE-017, STORE-034, STORE-036.
- Status: confirmed for the model: chronological, stacked, the only way to remove, relocate or permanently add something to the metaform, never toggled, a middle layer never deleted, removal by peeling from the top and rebuilding or by another layer on top, one provenance record each. Confirmed also: correction layers sit underneath and knowledge layers on top, a correction never changes a knowledge layer's things, an item left with nothing to attach to is orphaned and not shown, and an element put back at the same address shows again what was attached to it. Restoring the same element identity when an element is put back is recommended. Whether a removed join shows again when its receiver and provider both exist again at the same places is open question 14. The storage mechanics, and raw reads listing orphans marked as orphaned, are recommended.
### LAYER-012 Memory is a mutable layer with no provenance

- Requirement: Memory is a mutable layer whose items change in place and carry no provenance.
- What this means: Memory is agents' working notes, kept at the node they concern. Memories tied to places in the metaform belong to no single agent: any agent may read them and add to them, because they exist to share knowledge. Every element and every join can be a root of memory, and memories connect to each other through relations, LAYER-013. Naming a node is enough to attach a memory there; the memory module makes the link to the node itself, and no agent builds it. One memory at a node corrects a small wrong inference right where agents read it, so the map does not have to be perfect to be useful. Memory takes part in select and mask like any other layer, so a job can include it or mask it on a branch.
- Why: Memory's value is being cheap to add and to fix. History and provenance would make every note heavy.
- How it shows: An agent adds an observation at an element, and the next agent reading that element receives it. Editing or deleting a memory changes it immediately, and no history is kept.
- Build: The memory layer is created per metaform, MAP-045, on the first memory write, with kind memory, mutable true and transitive false; its name, module and variable are in STORE-020. It has no provenance record, and LAYER-010's refusal does not apply to it, because it is recognized by its kind. Updates and deletes change the stored item in place.
- Acceptance: After an update, a read returns only the new text, and no earlier version is stored.
- Relates to: LAYER-013, LAYER-007, LAYER-010, STORE-018.
- Status: confirmed. Transitive false for memory is recommended.

### LAYER-013 Memory follows the MCP reference memory server's interface

- Requirement: Memory offers the operations of the MCP reference memory server, and its nodes are the map's elements and joins.
- What this means: The reference interface has entities with a name, a type and observations; relations with a from, a to and a relation type; and operations to create entities, create relations, add observations, delete entities, delete observations, delete relations, read the graph, search nodes and open nodes. In Metaform, an entity is an element or join of the map, named by its address or join id, and observations are memory items attached there. A relation is a memory item linking two nodes with a relation type.
- Why: Agents already know this interface. Putting memory on the map's own nodes means a note lands exactly where the next agent reads, instead of in a separate graph that has to be matched back to the map.
- How it shows: An agent calls open nodes on an element address and receives that element with its observations and relations. Search finds nodes by the text of their observations.
- Build: Each operation maps onto the memory layer's items at the named nodes, through the memory module, BASE-040, on the CLI and over MCP from one declaration. Open nodes and search are direct reads under LAYER-008. Subtypes and type addresses may also be named as nodes, which is recommended in STORE-020.
- Acceptance: Add observations at an element, then open nodes at the same address, returns those observations.
- Relates to: LAYER-012, LAYER-008, STORE-020, MCP-003.
- Status: confirmed. What create entities does for a name that is not a node of the map is open.

### LAYER-014 Native and latent reasoning are separate layers

- Requirement: Native reasoning and latent reasoning each produce their own layer, each with its own provenance record.
- What this means: The native agent builds the map from the artifact. The latent agent receives everything the native agent built, the elements, descriptions, joins and operative purposes, and reasons from outside the native frame, blind to the implementation particulars. It can agree with what it sees, question it, or infer missing and different relationships. Its output is its own layer.
- Why: The latent perspective is valuable because it differs from the native one. Separate layers keep the two from blending, and selecting both puts them side by side when a reader wants to compare.
- How it shows: The native layer's provenance is sighted, and the latent layer's is blinded. A view selecting both shows where they differ.
- Build: The latent run creates a new layer with blinded true, writing its items against the native layer's nodes and creating new elements and joins in its own layer where it infers them.
- Acceptance: A latent run leaves the native layer unchanged and adds exactly one new layer with its own provenance.
- Relates to: LAYER-009, LAYER-010, LAYER-015.
- Status: confirmed.

### LAYER-015 The blind-spot challenge workflow

- Requirement: A blind-spot challenge runs in two passes and one approval: a critic builds the blind-spot layer, a project agent answers each challenge A, B or C through the MCP server, and the user approves B answers, which then become plans.
- What this means:
  - Pass one, the critic. An unembroiled critic, working blind from the metaform or with the artifact's context, traverses the metaform and writes a challenge wherever it sees a blind spot. Blind, sighted or both is an option of the run, and each critic run builds its own blind-spot layer with its own provenance. A challenge that proposes new functionality carries the new element and its join, joined to the metaform on either side, MAP-044. The critic defines the blind spots and answers none of them.
  - Pass two, the answer. A project agent answers each challenge through the MCP server with one of three answers, each an equal choice. A: not beneficial, it was considered and is not an oversight. B: beneficial, it should be taken up. C: handled by X, where X is a link to the existing element or join that already does it.
  - Approval. The user approves B answers. An approved B becomes a plan. A and C stay recorded as answered, so no later agent raises them again as if they had been missed.
  - States. A challenge is open, answered A, answered B, answered C, or plan. Only a blind spot needs approval to become a plan. A plan an agent adds directly is pre-accepted and needs no approval.
- Why: Bias does not come from seeing the code. It comes from the role: an agent that sees a problem as its own to deal with defends the current work or reaches for the answer that closes its task, and gaming is part of that. So the blind spots are defined by a critic that owns nothing it judges, and the project agent, which knows the project, answers them. The blind critic notices what should exist because of what the artifact is; the sighted critic notices what the artifact already does that the map never named. Approval stays with the user because a B answer is the project agent agreeing to new work, and turning that into a plan is the owner's decision.
- How it shows: After pass one, a blind-spot layer holds challenges, all open. After pass two, every challenge shows its answer next to its layer name. After `metaform map approve <challenge>`, the B challenge reads as plan, and any element and join it carries read as plan.
- Build:
  - The workflow is module work; the chassis supplies the layers, items, links, provenance and challenge states it uses. A challenge is an item in the critic's blind-spot layer, STORE-015, attached to the element or join where the blind spot is seen, or to the new element it proposes. The blind-spot layer is built and locked by the critic like any knowledge layer, LAYER-018.
  - Answers and approvals are recorded as challenge state, STORE-040, not as edits to the critic's blind-spot layer.
  - `answer` is a map verb and MCP tool: challenge, A, B or C, and for C a link to an existing element or join. A C answer without that link is refused.
  - `approve` is a map verb declared for the CLI only, `surfaces=('cli',)`, BASE-035, so it is never an MCP tool and an agent working through MCP cannot approve its own answers. It is the one place a person acts. It accepts only a challenge answered B.
  - A plan an agent adds directly is recorded as a plan with no challenge, STORE-040.
  - Every read that returns a challenge, or an element or join a challenge carries, shows its state next to its layer name.
  - The critic prompt gives the metaform and asks for blind spots; the answer prompt gives each challenge and the three answers as equals. The provenance of each blind-spot layer records the critic's role and whether it was blinded.
- Acceptance:
  - A C answer without a link to an existing element or join is refused.
  - `approve` is absent from the MCP tool list, and on the CLI it refuses a challenge that is open or answered A or C.
  - After `approve` on a B challenge, reads show that challenge and the element and join it carries as plan; the blind-spot layer's items are unchanged.
  - A plan added directly by an agent reads as plan without any approval.
- Relates to: LAYER-009, LAYER-010, LAYER-014, LAYER-016, LAYER-018, MAP-044, STORE-015, STORE-040, BASE-035, BASE-038.
- Status: confirmed for the two passes, the approval, the answers and the states. Recommended: challenge state kept in STORE-040, `answer` and `approve` as map verbs, `approve` on the CLI only, and the blind critic as the default when no option is chosen.

### LAYER-016 Knowledge layers carry whatever their prompt asks for

- Requirement: A knowledge layer is freeform: it holds whatever its prompt asks to be placed there and may create new namespace objects of any kind, and every item in it attaches to the metaform, at an element or join or at a new object the layer creates that is itself linked to the metaform.
- What this means: The functional map holds only functional types. A knowledge layer is not bound by that. Its content is whatever the prompt that builds it asks for: imperatives, best practices, foresight, a specification at each node after ingesting a paper, or anything else. Those are examples, not a closed list, and the layer's one variable is what its prompt defines, LAYER-002. A knowledge layer carries new namespace objects related to whatever it concerns, and those objects can be pure encounter, medium, encoding, or whatever the prompt asks for; the functional map's address rules, MAP-013, do not apply to them. Every knowledge layer attaches to the metaform: each item links to an element or join of the metaform, or to a new object the layer creates, and that new object is itself linked to the metaform. What a layer holds, and how its agent was prompted, is up to the prompt. For example, a prompt can have an agent apply the intake's reasoning to find blind spots and create new encounter-function objects in its layer, each linked to the part of the metaform it concerns. A knowledge layer is often produced by one prompt applied at every element and every join. How completely it covers the map depends on the prompt: an open-ended prompt gives open-ended coverage, and a prompt that asks for at least one item per join gives one per join. It is built by an agent following its prompt, freely edited until the task is done, then locked and toggled on when needed through select and mask, LAYER-018. A knowledge layer can add new function joins that extend the metaform. Such a join is a normal function join: its receiver owns it, a provider serves it, and it is stored with the id of the layer that added it. It extends the metaform wherever that layer is toggled on, subject to select and mask; when the layer is off, or masked at the join's receiver, the join is absent from every read in context. Every join is noted with where it is from: every read that returns a join shows the name of the layer it comes from, so an agent always sees whether a join belongs to the intake map or to a knowledge layer, and to which one. A knowledge layer sits on top of the metaform as the correction stack leaves it, LAYER-011. If a correction removes or relocates what one of its items or joins attaches to, and nothing is left to attach to, that item or join is orphaned: stored, but not shown in context.
- Why: Keeping non-functional knowledge out of the map keeps the map's types clean, while layers put that knowledge exactly where an agent reads. A layer's joins extend the map only where the layer is chosen, and naming their layer on every read keeps the intake map and every extension distinguishable, so an agent weighs a join knowing what produced it. Leaving the content to the prompt is what makes a layer useful for any job, and generating a layer node by node reuses the map's structure as the plan for the work.
- How it shows: A layer built from a prompt asking for porting concerns returns them at each element it covers; an element under `code` can carry a knowledge object for the language in use, which the functional map would never hold. Without the layer selected, the same element shows none of it.
- Build: A knowledge item is either a property, transitive and attached to an element, including an element the knowledge layer created and linked to the metaform, STORE-039, or a function, a join in the layer, STORE-010, MAP-022. Each knowledge layer is an ordinary layer, LAYER-001 to LAYER-004, with one provenance record, LAYER-010, built and locked as LAYER-018. An item attaches at an element, join or subtype of the metaform, or at an element or join the same layer created, LAYER-003; an element the layer creates that carries a function or a purpose is linked to the metaform by a join in the same layer, on either side, MAP-044, and never by the namespace tree, because functions are not transitive; only an element created at a namespace prefix to hold properties is linked by the namespace tree itself, MAP-022. The chassis supplies no kind-specific behavior and does not check the content or the addresses of the objects a knowledge layer creates beyond address form, MAP-010. Whether an element a knowledge layer creates carries an intake role is D48; carrying none is recommended.
- Acceptance:
  - A layer written with one item at every join of a map returns, for each join, exactly the item written there.
  - A knowledge layer creates an element at a medium address, such as one naming a programming language, linked to an element of the metaform, and it is stored and readable in that layer, while the intake map is unchanged.
  - A finished knowledge layer adds a function join between two elements of the intake map. With the layer toggled on, the receiver's `joins` read in context returns that join with the knowledge layer's name, and returns the intake map's joins with the intake layer's name. With the layer toggled off, or masked at the receiver's address, the same read does not return the join, and a raw read still returns it with its layer name.
- Relates to: LAYER-001, LAYER-002, LAYER-003, LAYER-005, LAYER-007, LAYER-018, LAYER-019, MAP-013, MAP-044, STORE-025.
- Status: confirmed: knowledge layers are freeform, content is whatever the prompt asks, objects are not limited by function, every item attaches to the metaform, a knowledge layer can add function joins that extend the metaform, and every join is noted with the layer it comes from. How a created object is linked, by a join or an item in the same layer, and the read mechanics in STORE-025 are recommended. Producing specific layers is module work, pending D44.

### LAYER-017 Prompts and workflows are preprocessed against the metaform

- Requirement: A prompt or workflow handed to a working agent can be preprocessed against the metaform, so its wording names the project's own elements and it carries the namespace addresses and the knowledge layers the orchestrator chose.
- What this means:
  - Prompt preprocessing: every instruction is followed by the namespace addresses it concerns, as a footer that points into the MCP server, and between the prompt and that footer sit the layers of knowledge the main agent wants the working agent to have.
  - Workflow preprocessing: a subagent takes a workflow and rewrites its wording so it speaks directly to the project, prelinking proper nouns to their namespace addresses, inserting text from the metaform inline, adding knowledge-layer imperatives, and giving reference links into the MCP server. The layers of inference a step needs are collected in advance.
  - Workflows written this way run in any host that can run an agent, because the workflow carries its own context.
  - A workflow intake agent ingests a workflow and decides when handing work to another agent helps, and whether that next agent is blind to the repository. A workflow can be as simple as one canonical prompt, such as the one that writes the bias blind-spot layer.
  - The orchestrator chooses exactly which knowledge layers are available for a job, through select and mask, LAYER-007.
- Why: The working agent starts from project-specific wording and prepared knowledge instead of reconstructing them, which is the orientation cost Metaform exists to save, MAP-005. Namespace addresses are perfectly indexed proper nouns, so linking them costs almost nothing and removes ambiguity.
- How it shows: A preprocessed prompt names the project's elements by their readings and ends with their addresses; the chosen layers appear between the prompt text and the footer.
- Build: Module work, pending the workflow module's own spec, D44. The chassis supplies the reads it needs: addresses and readings, MAP-012; layers at a node, LAYER-008; and selection, LAYER-007.
- Acceptance: Belongs to the workflow module's spec.
- Relates to: MAP-005, MAP-012, LAYER-007, LAYER-008, LAYER-015, LAYER-016.
- Status: confirmed as design; deferred for the first working test.

### LAYER-018 Knowledge layers are written through one read-write tool

- Requirement: Knowledge layers are created, read, changed and removed through one read-write tool, the only tool that makes a new layer; every call names the layer it works on, and an agent with the tool can edit any knowledge layer at any time.
- What this means: Building a knowledge layer is a different path from intake. The intake is one submission, BASE-039. A knowledge layer is assembled object by object: the agent creates the layer, attaches items, properties, elements and joins, reads back what it wrote, and changes or removes any of them, one at a time, with calls that take named arguments. That is why objects are individual and a knowledge layer is never submitted all at once. Every call names the layer being built or edited. Agents are not assigned a layer and there is no ownership check: an agent is trusted to work on the layer it was told to work on. An agent that has the tool can go back to an existing layer and edit it, on its own judgment or because it was prompted to. Who can write is decided only by who has the tool, through tool permissions and the command surface, never by the layer's state. When the agent's task is done it marks the layer finished; a finished layer is listed as ready and can be toggled on, LAYER-019, and it stays editable through the tool. The layer's one provenance record, module and workflow, prompt, model, role, blinded, describes how the layer was created. Function joins the layer adds extend the metaform wherever the layer is toggled on, each shown with the layer it comes from, LAYER-016. Correction layers never change a knowledge layer, and anything in it left with nothing to attach to after a correction is orphaned, LAYER-011. Correction layers keep their own rules, LAYER-011, and memory keeps its own interface, LAYER-012 and LAYER-013.
- Why: The model builds incrementally against its prompt and fixes its own work as it goes, so it needs to add, change and remove single objects. Returning to a layer later, by the same agent or another one prompted to, is how knowledge improves. Controlling access by the tool keeps one rule that holds for every agent and every harness, and trusting the agent to name its layer avoids assignment machinery the design does not have.
- How it shows: An agent with the tool creates layer `practices-cpp`, adds a property at an element, reads the layer by name, changes the property, removes a join it created, and marks the layer finished. It appears as ready in `metaform map layers` and can be toggled on. Later another agent with the tool edits one of its items, and the next in-context read shows the change. An agent without the tool has no way to create or change a knowledge layer.
- Build: One map verb, `knowledge`, served as the single MCP tool `map_knowledge`, BASE-038, with an operation noun: `create`, `add-element`, `add-join`, `add-subtype`, `add-property`, `add-item`, `add-ref`, `edit`, `remove`, `finish`, `tag`, `untag` and `discard`. Every operation names the layer. The store operations are STORE-024 and STORE-032. The tool is granted or withheld like any tool, through the command surface, CLI-022, and harness permissions.
- Acceptance:
  - A layer built with an add, an edit and a removal, then finished, reads back exactly the final state.
  - Before `finish`, the layer's items are absent from another agent's node read in context; after `finish` they are present when the layer is toggled on and absent when it is off or masked.
  - After `finish`, `edit` through the tool changes the item in place and the next in-context read shows the change.
  - With `map` narrowed off the command surface, `map_knowledge` is not listed and a call to it is refused.
- Relates to: LAYER-001, LAYER-007, LAYER-010, LAYER-011, LAYER-012, LAYER-016, LAYER-019, STORE-024, STORE-032, BASE-038, CLI-022.
- Status: confirmed for one read-write tool that alone makes new layers, every call naming its layer, no assignment or ownership, editing any existing knowledge layer with the tool, access by tool only, and toggling on and off. Finishing as marking a layer ready without making it immutable, and the single tool with an operation noun, are accepted as the technical answer and confirmed. The operation names are recommended.

### LAYER-019 Layers are tagged, listed and toggled
- Requirement: Every layer carries tags; layers can be listed and filtered by tag, kind and module; and the layers active for a piece of work are toggled on and off by name or by tag.
- What this means: A layer carries any number of tags, short words that say what it is for, such as `practices`, `foresight`, `porting` or `mgm-review`. Tags are given when the layer is built and can be added or removed at any time, including after the layer is finished, because tags are for finding and toggling layers and are not part of the layer's content. Listing shows every layer with its name, kind, module, tags, whether it is building or ready, whether it is hidden, and whether it is toggled on for the current context, and it filters by tag, kind and module. Toggling decides which layers are on: the toggled set is the starting selection at the trunk, LAYER-007, and per-address select and mask apply on top of it. A tag toggles every layer that carries it. Correction layers are never toggled: they are always applied, in order, LAYER-011. The orchestrator takes a prompt and toggles on and off whatever layers it wants for that work. Choosing is the orchestrator's job, done by how it is prompted: Metaform provides the tags, the listing and the toggle, and nothing in Metaform decides which layers a piece of work gets.
- Why: Knowledge layers are only useful when the right ones reach an agent for the job in hand. Tags let an orchestrator find layers by what they are for without knowing every layer's name, and toggling lets one project carry many layers while each job sees only the ones chosen for it. Keeping the choice with the orchestrator keeps judgment where the prompt is, and adds no machinery that second-guesses it.
- How it shows: `metaform map layers tag=practices` lists the practice layers with their state and whether each is on. `metaform set --layers practices,memory` turns on every layer tagged `practices` and the memory layer for this folder; an in-context read then returns those layers and no others, subject to select and mask at each address. `metaform unset --layers` returns to every finished layer that is not hidden.
- Build: Tags are stored as in STORE-038, listed through the `layers` read, STORE-025, and edited with the map module's `tag` and `untag` verbs, BASE-038. Toggling is the `--layers` context setting, CLI-033. A building layer is never toggled on, and a hidden layer stays out even when toggled, LAYER-006.
- Acceptance:
  1. A layer finished with tag `practices`, then given tag `mgm`, lists with both tags; its content and provenance are unchanged.
  2. With two finished layers A tagged `practices` and B untagged, `set --layers practices` makes an in-context node read return A's items and not B's; `unset --layers` makes it return both.
  3. With `--layers` naming A and a mask of A at `code.engine`, a read at `code.engine.game` omits A.
- Relates to: LAYER-006, LAYER-007, LAYER-016, LAYER-018, STORE-013, STORE-019, STORE-025, STORE-035, STORE-038, BASE-038, CLI-021, CLI-033, MCP-024.
- Status: confirmed that layers are tagged, listed and toggled on and off, and that the orchestrator chooses which layers a piece of work gets. Tags being editable after locking, the listing fields and filters, and toggling as the `--layers` setting are recommended.

## Open questions

1. Are mutable, hideable and transitive fixed for each kind of layer, so memory is always mutable and never transitive, or does the module choose them for each layer it creates?
2. Does hiding a layer also hide the layers built from it? Recommended: yes.
3. Dependents are re-examined after a correction layer is applied, and hiding may follow dependencies. Both need to know which layers a layer was built from. Recommended: the layer record holds the list of source layers, and the correction stack position it was built against, as part of the one record per layer. Is that acceptable, or should it live elsewhere?
4. For a layer a person writes directly, with no model or prompt, what does its provenance record hold?
5. When a second run adds items to an existing layer, is that the same layer with its one record, or a new layer with its own?
6. Does a join have its own select and mask, or does it use its receiver's? Recommended: the receiver's.
7. What does the memory operation to create entities do for a name that is not a node of the map?
8. Answered: a proposed element never enters the intake map. It stays in its blind-spot layer, and an approved B answer makes it a plan there, LAYER-015.
9. Can a single item inside a layer be hidden, or only a whole layer?
10. Properties attach only to elements, and a property at a prefix with no element goes on an element the layer creates there, MAP-022. Can any other layer item, such as a memory or a challenge, attach at a type address that no element holds?
11. Answered: a C answer's link to the handling element or join is kept with the challenge state, STORE-040, LAYER-015.
12. Properties carry transitivity, MAP-022, LAYER-005. Does a layer still declare a transitive flag for its other items, such as memories or challenges, or is transitivity only a property's, so the flag is removed?
13. Answered: a correction layer never changes a knowledge layer's things. Correction layers sit underneath, knowledge layers on top, and an item left with nothing to attach to is orphaned, LAYER-011.
14. A removed join whose receiver and provider both exist again at the same places: does it show again, as an element put back at its address does, or does it stay removed until a correction adds a join? (LAYER-011, STORE-017)
