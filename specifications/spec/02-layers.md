# 02 Layers

This section defines layers: what a layer is, how it attaches to the map, its declared properties, how select and mask decide what reaches each point, how layers are read, provenance, memory, corrections, native and latent reasoning, and the blind-spot challenge workflow.
The receiver, purpose and encounter structure itself, element identity and subtypes are in section 01; storage tables and indexes are in the storage section; the operations a module calls are in the common base section.

### LAYER-001 Everything Metaform holds is a layer

- Requirement: Every piece of knowledge Metaform holds belongs to exactly one layer, the intake's map included.
- What this means: A layer is a named body of inferred knowledge laid over the map. The intake produces a layer too: its layer is the one that creates most elements and joins. Every element, join, subtype and layer item records the layer that produced it. The core map is the selection of the intake layer. A new element proposed by a later pass lives in that pass's layer.
- Why: When everything is a layer, every piece of knowledge attaches, selects, hides and records its origin the same way. That uniformity lets modules compose, and it keeps the map from becoming a special case that every module has to handle separately.
- How it shows: Asking for an element's or join's origin always names one layer. Selecting only the intake layer shows the core map with nothing else on it.
- Build: The layer record holds: id, name, the module that owns it, variable (LAYER-002), mutable, hideable, transitive (LAYER-004), and created time; an intake layer also holds the intake result id (MAP-040). The project is the store the layer lives in (STORE-003), and hidden state is kept as in STORE-013. Every element, join and subtype record carries a layer id, never empty. Every layer item record carries a layer id, never empty. The intake writes its elements, joins and subtypes under one intake layer created at the start of the intake run. That layer stays open, invisible to reads in context, until the run completes it, STORE-032, so the map appears whole or not at all.
- Acceptance:
  - After an intake through MCP, every stored element, join and subtype names the intake layer, and reading the intake layer returns all of them.
  - Storing an element, join, subtype or layer item without a layer is refused.
- Relates to: LAYER-002, LAYER-003, LAYER-008, MAP-040, STORE-013, STORE-014.
- Status: confirmed.

### LAYER-002 A layer carries one inferred variable

- Requirement: Each layer answers exactly one question, and every item in it is an answer to that question at the place it attaches.
- What this means: The variable is the one thing the layer infers. For example: a blind-spot challenge at each node, a verdict on each proposal, best practices for a type, porting concerns for a move to another language, or an agent's memory. A layer never mixes two variables. Two questions make two layers.
- Why: A layer with one variable can be selected, masked, hidden, compared and trusted as a unit, because everything in it was produced the same way for the same purpose. That is what makes layers compose: a module adds its one variable without knowing about any other module, and select and mask decide which layers an agent sees together.
- How it shows: Every layer states its variable in one sentence. Reading a layer returns items that all answer that sentence.
- Build: The layer record's variable field is required text, stating the question. The operation that creates a layer refuses an empty variable.
- Acceptance: Creating a layer without a variable is refused.
- Relates to: LAYER-001, LAYER-003, LAYER-009.
- Status: confirmed.

### LAYER-003 A layer item attaches on an element, on a join, or on a new element and join

- Requirement: Each layer item attaches at one element, one join, or one subtype, or it creates a new element and join and attaches there.
- What this means: Where an item attaches is where it says something. An item about what an element is attaches at the element. An item about how a provider serves a receiver attaches at their join. An item about an absorbed part attaches at its subtype directly. When a layer's answer is something the map does not contain yet, the layer creates the element and its join, and those new records belong to that layer.
- Why: Attaching where the knowledge applies means an agent reading any node receives exactly what was inferred about it. Allowing a layer to create its own element and join means a module can extend the map without special machinery, which is the same way the intake builds the map.
- How it shows: Reading an element returns the items attached there. Reading a join returns the items attached to that join. An element created by a later layer shows that layer as its origin.
- Build: A layer item record holds: id, layer id, attach kind (element, join or subtype), attach id, value, and the revision fields of LAYER-011. The value is text or a structured document. Attach id refers to the stable id of the element, join or subtype, never to its address, so items follow an element through retyping. An item cannot attach to a missing target.
- Acceptance:
  - An item attached to an element stays attached after the element's type address changes.
  - An item attached at a subtype is returned by a read of that subtype and not by a read of its parent element.
- Relates to: MAP-015, MAP-031, LAYER-001, LAYER-008, STORE-015.
- Status: confirmed for elements, joins, subtypes, and new elements and joins. Whether an item may also attach at a type address that no element holds, as LAYER-005 and MAP-011 use, is open; see open question 10.

### LAYER-004 A layer declares its properties

- Requirement: Each layer declares whether it is mutable or immutable, whether it is hideable, and whether it is transitive, and the chassis applies those rules the same way for every layer.
- What this means:
  - Mutable: its items change in place. Memory is mutable.
  - Immutable: its items change only by correction, as superseding revisions (LAYER-011). The intake layer is immutable.
  - Hideable: the layer can be hidden from views and agent context while its content and history stay stored (LAYER-006).
  - Transitive: its items travel along the namespace tree as described in LAYER-005.
- Why: Declaring the behavior on the layer lets the chassis apply revisions, visibility and propagation once, uniformly. No module rebuilds these rules, and no module can apply them differently.
- How it shows: A layer's properties are listed with it. Trying to edit an item in place in an immutable layer is refused with one next step naming the correction operation.
- Build: Three required boolean fields on the layer record, mutable, hideable and transitive, set when the layer is created. The chassis enforces them in every write and read path.
- Acceptance:
  - An in-place edit of an item in an immutable layer is refused and names the correction operation.
  - A transitive item at a parent address is received at a child address; a non-transitive one is not.
- Relates to: LAYER-005, LAYER-006, LAYER-011, LAYER-013.
- Status: confirmed that layers declare these properties. Whether each property is fixed for a kind of layer or chosen by the module for each layer it creates is open.

### LAYER-005 Transitive items apply down the tree and are visible up toward the trunk

- Requirement: A transitive layer item placed at a namespace address applies to every address beneath it, and is visible, without applying, at every address above it toward the trunk.
- What this means: Inheritance runs one way. A practice for `code` holds for every engine, every game engine and every FPS engine. A practice for `code.engine.game.fps` means nothing for code in general. Toward the trunk, the item is visible without applying: C++ attached at the engine and Bash attached at the installer both show at `code`, so `code` shows every medium in use in the project, yet the installer does not inherit C++ because C++ is visible at `code`. Where an item is placed is therefore strategic. Placed near the trunk, it applies to every branch after it. Placed further from the trunk, the branches beside it do not inherit it. An item that still holds with its leaf segment removed belongs higher in the tree.
- Why: Every prefix of an address is a complete type with its own inference, and practice passes from parent to child. Visibility toward the trunk lets a broad question see everything in use beneath it without spreading a branch's specifics to its siblings.
- How it shows: Reading an address lists the transitive items that apply there, and separately the items visible there from beneath.
- Build: Transitive travel follows the namespace tree only, never the purpose graph, so it always terminates. For an address A, the applying set is the transitive items attached at A and at every prefix of A, after select and mask. The visible set is the transitive items attached at any address that has A as a prefix, after select and mask. Reads return the two sets separately.
- Acceptance:
  - With C++ attached at `code.engine` and Bash at `code.installer`: `code` shows both as visible and neither as applying; `code.installer` does not receive C++.
  - An item at `code` applies at `code.engine.game.fps`.
- Relates to: LAYER-003, LAYER-004, LAYER-007, MAP-011.
- Status: confirmed.

### LAYER-006 Hiding removes a layer from view and keeps it stored

- Requirement: A hideable layer can be hidden and shown again; hiding removes it from every view and agent context and deletes nothing.
- What this means: Hidden knowledge stays stored with its history and provenance, and it can be shown again at any time. A port from C++ to Rust hides the C++ layers and selects the Rust layers; addresses and purposes stay unchanged.
- Why: Knowledge that no longer applies must stop steering agents without being lost, because it may apply again and because its history explains why things are the way they are.
- How it shows: After hiding a layer, no read, view or context assembled for an agent contains its items. Showing it restores them unchanged.
- Build: The layer's hidden state, stored as in STORE-013. Every read path and every context assembly path filters hidden layers out. Hiding a layer that is not hideable is refused with one next step.
- Acceptance: A hidden layer's items appear in no element read, join read, layer-at-node read or MCP read, and reappear unchanged when it is shown.
- Relates to: LAYER-004, LAYER-007, STORE-013.
- Status: confirmed for hiding a layer. Hiding is of whole layers only, per D20's recommendation. Whether hiding a layer also hides the layers built from it is open.

### LAYER-007 Select and mask decide which layers reach each address

- Requirement: At each namespace address, the effective selection is (incoming & mask) | select, computed from trunk to leaf, and it applies on every path by which knowledge reaches an agent.
- What this means: Selection is a set of layers. The project supplies the starting selection at the trunk. At each address, a mask can block layers coming down from above, and a select can turn layers on from that address downward. An address with no select and no mask passes its incoming selection through unchanged. A mask on `code.engine` can block porting notes for everything under it, and `code.engine.renderer` can select them again for itself. The same selection governs direct element reads, property and provider context, workflow context and MCP reads. A layer excluded at an address cannot reach an agent there through a property or provider path.
- Why: Select and mask let one map serve many jobs, each seeing exactly the knowledge meant for it at each place, without copying knowledge or building a separate map per job. Applying the same rule on every path is what makes the selection trustworthy: an excluded layer that leaks in through a side path defeats it.
- How it shows: Two jobs with different starting selections read the same element and receive different layers. Selecting a layer at a child address makes it appear there and below, and nowhere else.
- Build:
  - A selection entry holds: project, address, layer id, kind (select or mask). A mask entry names a layer blocked at that address; the mask applied is all layers except those named.
  - Resolution at address A: start with the project's starting selection; for each prefix of A from the trunk to A itself, set selection to (selection minus the layers masked there) plus the layers selected there.
  - Resolution follows the namespace tree only, never the purpose graph.
  - An element's effective selection is the effective selection at its address. Every context assembly path calls this one resolution.
  - The project's starting selection is stored as in STORE-035; when none is stored, every complete layer starts selected.
  - Selection data that cannot be applied faithfully, a select or mask row whose layer is hidden or still open, is kept and reported as unresolved by the resolution read, STORE-035, never replaced by a broad default.
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
- What this means: Two perspectives on the same nodes, such as a blind critic's verdicts and a sighted critic's verdicts, are two layers. Selecting both at a node puts them next to each other. Where they disagree is found by the view reading both layers, not by a record holding both answers.
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
- How it shows: Asking for any layer's origin returns one record. Two critic layers over the same proposals show two records, for example one blinded and one sighted, each with its role.
- Build: The provenance record holds: layer id (unique), module, workflow, prompt (the full text as delivered), model, role, blinded. It is written when the layer is created, by the operation that creates it. A layer other than memory cannot be created without it.
- Acceptance:
  - Creating a non-memory layer without provenance is refused.
  - Writing a thousand items to a layer leaves exactly one provenance record for it.
- Relates to: LAYER-012, LAYER-014, LAYER-015, STORE-016.
- Status: confirmed. What the record holds for a layer written directly by a person, with no model or prompt, is open. Whether a second run adding items to an existing layer is the same layer or a new layer is open.

### LAYER-011 Immutable layers change by superseding revisions

- Requirement: An item in an immutable layer changes only by a correction, stored as a new revision that supersedes the old one, and current is a pointer to the newest revision.
- What this means: The earlier revision stays stored and readable. Reads return the current revision unless a revision is asked for. Knowledge built on the corrected item is re-examined and never rewritten: layers that depend on it are marked for re-examination, and their contents stay as they were until someone re-examines them.
- Why: The map is the shared foundation, so a change to it must be explicit and traceable. Rewriting dependents silently would put inference into them that nobody performed; marking them keeps every stored answer honest about what it was built from.
- How it shows: After a correction, reads show the new value, and the item's history shows both revisions. Layers built on the corrected layer show that they need re-examination.
- Build: The layer item record carries revision number and supersedes (the prior revision's id), and a current pointer per item names the current revision. A correction writes a new revision and moves the pointer in one transaction. Elements, joins and subtypes in an immutable layer follow the same rule. The dependency marking and how it is cleared are STORE-036, which reads the list of source layers described in the open questions.
- Acceptance:
  - A correction leaves the old revision readable and the pointer on the new one.
  - A correction changes no item in any other layer.
- Relates to: LAYER-004, LAYER-010, MAP-015, STORE-017.
- Status: confirmed. The unit of revision being the item is recommended. How a layer records which layers it was built from is open.

### LAYER-012 Memory is a mutable layer with no provenance

- Requirement: Memory is a mutable layer whose items change in place and carry no provenance.
- What this means: Memory is agents' working notes, kept at the node they concern. Memories tied to places in the metaform belong to no single agent: any agent may read them and add to them, because they exist to share knowledge. Every element and every join can be a root of memory, and memories connect to each other through relations, LAYER-013. Naming a node is enough to attach a memory there; the memory module makes the link to the node itself, and no agent builds it. One memory at a node corrects a small wrong inference right where agents read it, so the map does not have to be perfect to be useful. Memory takes part in select and mask like any other layer, so a job can include it or mask it on a branch.
- Why: Memory's value is being cheap to add and to fix. History and provenance would make every note heavy.
- How it shows: An agent adds an observation at an element, and the next agent reading that element receives it. Editing or deleting a memory changes it immediately, and no history is kept.
- Build: The memory layer is created per project, on the first memory write, with kind memory, mutable true and transitive false; its name, module and variable are in STORE-020. It has no provenance record, and LAYER-010's refusal does not apply to it, because it is recognized by its kind. Updates and deletes change the stored item in place.
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

- Requirement: The blind-spot challenge workflow writes a challenge at every element and every join, collects proposed pieces, and has critics give each piece one verdict, A, B or C, each critic writing its own layer.
- What this means:
  - Challenge: a pass visits every element and every join and writes a bias blind-spot challenge there, in a challenge layer. Rendered as a prompt, the challenge asks what is missing at that node.
  - Proposals: the pieces proposed in answer are items in a proposal layer; a piece that is a new element and join lives in that layer.
  - Verdict: each proposed piece gets exactly one verdict from each critic that runs. A: not beneficial, it was considered and is not an oversight. B: beneficial, it should be considered for the project. C: handled by X, where X is a link to the existing element or join that already does it.
  - Critics: blind, reasoning from the map only; sighted and non-embroiled, reasoning from the map with the artifact available as evidence for one specific claim, the heavier operation; or both. Which critics run is an option of the workflow. Running both is an option, not a requirement.
  - Each critic writes its own verdict layer, with its own provenance. Where the critics disagree is a view over the two layers.
- Why: Bias does not come from seeing the code. It comes from the role: an agent that sees a problem as its own to deal with defends the current work or reaches for the answer that closes its task, and gaming is part of that. So the critic owns nothing it judges, no verdict turns into work for it, and no verdict is presented as more rewarded than another. The blind critic can notice what should exist because of what the artifact is; the sighted critic can notice what the code already does that the map never named, or a claimed handler that does not really handle it. Either can produce answers the other would not.
- How it shows: After a run, every element and join has a challenge. Each proposal has one verdict per critic that ran. A C verdict opens the element or join it names.
- Build: The workflow is module work; the chassis supplies the layers, links and provenance it uses. The verdict item value holds the verdict letter; for C, the item's link names the element or join that already handles it, STORE-015 and E8. The workflow refuses a C verdict without a link. The critic prompt gives the piece, the three verdicts as equals, and the map. The provenance of each verdict layer records the critic's role and whether it was blinded.
- Acceptance:
  - A C verdict without a link to an existing element or join is refused.
  - A run with both critics produces two verdict layers and leaves the challenge and proposal layers unchanged.
- Relates to: LAYER-009, LAYER-010, LAYER-014, STORE-015.
- Status: confirmed. The C verdict's link is held in the item's link fields of STORE-015, per E8, recommended; the verdict item's value holds the verdict letter. The blind critic as the default when no option is chosen is recommended. How an element proposed in a proposal layer becomes part of the core map is open.

### LAYER-016 Knowledge layers carry what the functional map leaves out

- Requirement: Knowledge layers hold non-functional and task knowledge at any address, element or join, including best-practice imperatives, foresight, and content generated by asking one question at every element and join.
- What this means: The functional map holds only functional types. Medium, encoding, practices, foresight and anything else an agent should know live in knowledge layers, which may link any address, MAP-013. Common kinds are best-practice imperative layers, thinking-with-foresight layers and memory layers. A knowledge layer is often produced by one prompt applied at every element and every join, for example project-specific best practices for each node and join, or, after ingesting a paper, a specification at each node for applying the paper's ideas. How completely such a layer covers the map depends on the prompt that produces it: an open-ended prompt gives open-ended coverage, and a prompt that asks for at least one item per join gives one per join.
- Why: Keeping non-functional knowledge out of the map keeps the map's types clean, while layers put that knowledge exactly where an agent reads. Generating a layer node by node reuses the map's structure as the plan for the work.
- How it shows: A best-practice layer returns practices when an agent reads an element or join; the same element without that layer selected shows none.
- Build: Each kind is an ordinary layer, LAYER-001 to LAYER-004, written by the module that produces it, with one provenance record, LAYER-010. The chassis supplies no kind-specific behavior.
- Acceptance: A layer written with one item at every join of a map returns, for each join, exactly the item written there.
- Relates to: LAYER-001, LAYER-002, LAYER-003, LAYER-005, MAP-013, LAYER-017.
- Status: confirmed as design. Producing these layers is module work, pending D44.

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
- Relates to: MAP-005, MAP-012, LAYER-007, LAYER-008, LAYER-015, LAYER-016, MCP-026.
- Status: confirmed as design; deferred for the first working test.

## Open questions

1. Are mutable, hideable and transitive fixed for each kind of layer, so memory is always mutable and never transitive, or does the module choose them for each layer it creates?
2. Does hiding a layer also hide the layers built from it? Recommended: yes.
3. Dependents are re-examined after a correction, and hiding may follow dependencies. Both need to know which layers a layer was built from. Recommended: the layer record holds the list of source layers, with the revision it read, as part of the one record per layer. Is that acceptable, or should it live elsewhere?
4. For a layer a person writes directly, with no model or prompt, what does its provenance record hold?
5. When a second run adds items to an existing layer, is that the same layer with its one record, or a new layer with its own?
6. Does a join have its own select and mask, or does it use its receiver's? Recommended: the receiver's.
7. What does the memory operation to create entities do for a name that is not a node of the map?
8. How does an element proposed in a proposal layer become part of the core map?
9. Can a single item inside a layer be hidden, or only a whole layer?
10. Can a layer item attach at a type address that no element holds? LAYER-005 and MAP-011 attach practices at addresses such as `code.engine`, while LAYER-003 lists elements, joins, subtypes, and new elements and joins.
11. Is a C verdict's link to the handling element or join held inside the item's value, as LAYER-015 states, or in the item's link fields, as STORE-015 has it?
