# 01 The map: concept, mesh, namespace, elements, joins and subtypes

Scope: what a metaform is, the receiver, purpose and encounter structure it is made of, the namespace of types, element identity and roles, the join and its fields, subtypes produced by annealing, how an intake result becomes these records and how it is judged, and the work recorded on the map: the condition of its objects, tasks, the work queue, questions and past work.
Out of scope here: layers, provenance, memory and corrections, in section LAYER; tables and indexes, in section STORE; the module-facing data access object, in section BASE.

## Terms

These terms are used exactly as defined in the Canonical Intake.
- AUE, Artifact Under Examination: the thing being examined.
- VE, Vested Entity: the party vested in the type of thing the artifact is. It receives joins and holds Operative Purposes.
- VRE, Vested Receiving Entity: an element acting as the receiver of a join.
- PE, Providing Element: the element at the other end of a join, whose Encounter Function serves the receiver's Operative Purpose. PE is a position in a join, not a role.
- OP, Operative Purpose: the why, held by the receiver in its join.
- EF, Encounter Function: the how, the provider's function for that specific encounter, stored in the receiver's join.
- DE, Defining Element; SE, Substantial Element; NE, Notable Element: roles of elements inside the AUE. A Substantial Element's encounter is a function, MAP-022.
- AT, Artifact Type. Type: a namespace address and the reusable functional meaning it names.
- Element: a project's realization of a Type. Join: the receiver-owned record of one encounter.
- Subtype join: the join that annealing places inside its parent functionality's purpose join, holding an absorbed element. It keeps its own encounter function and has no purpose of its own. The element it holds stays one ordinary element record and does not move, MAP-030. Subtype, where this spec says it alone, means a subtype join.

---

### MAP-001 C(T) is the theory behind how a metaform works

- Requirement: A metaform is built on the theory C(T) = { (r_i AND p_i AND e) }: a Type's identity is each Receiving Entity r_i bound to its Operative Purpose p_i and the Type's Encounter Function e. C(T) explains why the structure works; it is not a mechanism, and nothing in Metaform stores, computes or checks it.
- What this means: A thing is what it is because of who receives it, why they hold it, and how it serves them. The conjunction is exact: a receiver without its purpose, or a purpose without the encounter that serves it, is not part of the identity. A realization can change substantially and keep its identity as long as C(T) holds. Mutation changes the realization and keeps C(T). Transformation changes C(T), which means the thing has become something else. The map's records carry this theory in their shape: every join is one receiver's purpose served by a provider's encounter function, MAP-002 and MAP-020. There is no Type record that stores a single encounter function e, no C(T) field, no C(T) score and no C(T) read.
- Why: Placing identity in semantic relations, instead of in a frozen part of the content, lets the realization change freely while the identity stays stable. It also turns an inference-heavy question, what is this and what must it keep doing, into a structure an agent reads instead of reconstructs. Cost in Metaform means orientation inference an agent no longer has to spend. Because C(T) is theory, turning it into a stored value or a check would add a gate the design does not have.
- How it shows: The records are receivers, purposes and encounters. An agent that reads the joins an element provides sees who receives it, why and how, without any C(T) operation.
- Build: Nothing beyond the records it explains, MAP-002, MAP-020 and MAP-022. No field, table, read or check is named after C(T) or implements it.
- Acceptance: No write of an element or join is refused on the grounds that it changes C(T).
- Relates to: MAP-002, MAP-005, MAP-020, STORE-025.
- Status: confirmed.

### MAP-002 The functional map is a tripartite mesh that cannot express a cycle

- Requirement: Every join is one path receiver, then purpose, then encounter function, and the stored form of the map has no way to link back from a purpose or an encounter to a receiver.
- What this means: The three parts of a join are different kinds of thing, and the links between them run one way only: a receiver holds a purpose, and a purpose is served by an encounter. Nothing runs from an encounter back to a receiver. Because of that, a cycle cannot be written in the mesh at all. There is nothing to forbid and nothing to check. The encounter functions are specific to each encounter, so two joins that involve the same two elements in opposite directions are two separate paths with distinct purposes and distinct encounters, and they do not form a loop.
- Why: The structure enforces the design by what it can hold. A shape that cannot be expressed never needs a check, a rejection or a retry. A rejecting check sends agents into loops of retrying against it, and nothing in Metaform gates inference.
- How it shows: Walks over the mesh always end. No write anywhere reports a cycle.
- Build: A join record carries exactly one receiver element, one purpose, one provider element and one function. There is no field or record type that links a purpose or function to a receiver. The store performs no cycle detection on joins or elements.
- Acceptance:
  1. Two joins, A receives from B and B receives from A, with different purposes and functions, are both stored and both read back unchanged.
  2. The write path for joins contains no cycle check: adding the second join of the pair above succeeds without warning.
- Relates to: MAP-003, MAP-004, MAP-020.
- Status: confirmed.

### MAP-003 A join runs one way: the receiver owns it and the provider serves it

- Requirement: A join belongs to its receiver and names its provider, and it never runs in the other direction.
- What this means: Each join is one receiver's why served by one provider's how. When two elements need each other, they hold two different purposes, so they are two joins: one owned by the first element and served by the second, and one owned by the second and served by the first. Neither join is the other reversed. A join is stored with its receiver and is directly addressable within that ownership. A function's join can be moved, Rich 2026-09-27: mostly while annealing, otherwise to fix a serious misinterpretation or to follow a change in the design's structure. A moved join is the same join, with its id, its history and whatever is attached to it; its receiver, its provider, or the parent join a subtype join sits in, MAP-030, is what changes.
- Why: A single meaning per join keeps every join readable on its own and keeps the receiver, purpose and encounter structure acyclic. The Encounter Function is stored in the receiver's join because one provider may serve different receivers through different encounters. The join is where the map speaks about the artifact, so when understanding of which receiver a function serves improves, the join moves and keeps what was said about it.
- How it shows: Reading an element's joins as receiver returns the joins it owns. Reading them as provider returns joins owned by other elements. The two lists never mix. After a join is moved to another receiver, it is read under the new receiver with the same join id, and its memories and history come with it.
- Build: A join record has a stable join id, the receiver element id as owner, the provider element id, and the fields in MAP-020. A join is read by its id, by receiver, or by provider. There is no reverse or bidirectional join record. Nothing fixes a join's owner for life: a change of its receiver, provider or parent is a change of the same join, STORE-010 and STORE-034.
- Acceptance:
  1. Reading element A as receiver lists only joins A owns; reading A as provider lists only joins where A is the provider.
  2. A join moved from receiver A to receiver C keeps its join id and the memory attached to it, and is read under C and no longer under A.
- Relates to: MAP-002, MAP-020, MAP-030, STORE-010, STORE-034.
- Status: confirmed. A join can be moved and stays the same join: Rich, 2026-09-27.

### MAP-004 The element-to-element view is derived and may cycle

- Requirement: A view that collapses each join into a link from receiver element to provider element is derived from the joins when a feature needs it, and it may contain cycles.
- What this means: Some questions are about elements only, such as what depends on what. Collapsing joins into element links answers those, and in that view two elements that serve each other form a loop. That loop is real and correct. It belongs to the derived view, not to the mesh.
- Why: Real systems have mutual dependencies. Forcing the element view to be acyclic would mean deleting one of two true joins.
- How it shows: The dependency view of two mutually serving elements shows both links.
- Build: The element view is computed from current joins. It is never stored as its own structure and is never checked for cycles. Any feature that needs an order over it groups each cycle into one unit before ordering.
- Acceptance: None beyond MAP-002 acceptance 1.
- Relates to: MAP-002.
- Status: confirmed.

---

### MAP-005 A metaform is a multi-dimensional mesh that works through type understanding

- Requirement: A metaform is a non-manifold tripartite triangular mesh built from an ontological, linguistic typology, holding many C(T) at once and extended by layers, so that agents orient through type and function understanding instead of reasoning.
- What this means: Each join is a triangle of receiver, purpose and encounter, MAP-002. Triangles share elements without forming one closed surface, which is what non-manifold means here, and the map holds a C(T) for every Type in it, so it is many identities joined, not one. Layers add further dimensions over the same nodes, LAYER-001. Understanding what a type is and what a function does is primordial to a model: it happens without reasoning activating. Reading addresses as proper nouns, trunk to leaf and reversed, engages that understanding directly, MAP-011 and MAP-012. The prepared structure keeps work inside the basin of each subsystem, where a basin is the stable semantic definition C(T) of that subsystem: code can be mutated freely while its receiving entities and operative purposes stay the same. The same structure is a meta-prompting surface: prompts and workflows can be preprocessed against it, LAYER-017.
- Why: The cost Metaform saves is the inference every agent pays to orient itself in a project. Turning an inference-heavy operation, such as working around a frozen core or a gate, or finding one's place in a project, into a structure read at the level of type understanding leaves more of the agent's inference for higher-order reasoning. The shape itself guides agents, so the design needs no rejecting checks or approval gates, and agents work in flow rather than against blockers. Any token savings are a by-product, not the aim.
- How it shows: An agent given an element's address, its joins and its layers can say what the element is for and what must stay true about it without reading the implementation first.
- Build: Nothing beyond the records it explains: MAP-001, MAP-002, MAP-011, MAP-012 and LAYER-001. No component computes basins, embeddings or C(T); they describe why the structure works, MAP-001.
- Acceptance: None of its own. The acceptance of the records it names protects it.
- Relates to: MAP-001, MAP-002, MAP-011, MAP-012, LAYER-001, LAYER-017.
- Status: confirmed.

### MAP-006 Metaform engineers the context agents work in

- Requirement: Metaform is a context engineering tool: it engineers the context to install itself and the context of every subagent, and it enables true prompt-chained workflows enhanced by the Inference Metaform.
- What this means: Everything Metaform gives an agent is context prepared from the project's recorded understanding. Installing it writes the skill and the registration that tell an agent where Metaform's live instructions are, MCP-021. The composed instructions orient the agent that reads them, MCP-007, and a subagent reads its own instructions by name, unaltered, MCP-009. Prompts and workflows are preprocessed against the metaform so that each step speaks to this project and carries the knowledge it needs, and an orchestrating agent builds and runs the chain of prompts to improve the project itself, LAYER-017.
- Why: An agent works from the context it is given. When that context already holds the project's functional understanding, the agent spends its inference on its task instead of reconstructing the project, MAP-005, so every place Metaform meets an agent, its installation, its instructions and each step of a workflow, is a place to hand it that understanding.
- How it shows: An agent opened in a registered project learns from `metaform`, or from the server's instructions, what the project is and what to do next, and a subagent told a name reads its own instructions.
- Build: Nothing beyond the records it names: MCP-007, MCP-009, MCP-021 and LAYER-017.
- Acceptance: None of its own. The acceptance of the records it names protects it.
- Relates to: MAP-005, LAYER-017, MCP-007, MCP-009, MCP-021.
- Status: confirmed, 2026-09-11.

---

### MAP-010 The namespace is a tree of Types, and an address names a Type

- Requirement: A namespace address is a dotted path that names a Type, and the namespace is a tree in which each address's parent is the address one segment shorter.
- What this means: `code.engine.game.fps` names a Type. Its parent is `code.engine.game`, whose parent is `code.engine`, whose parent is `code`. The namespace is a typological ontology, not a taxonomy: it has no filler levels such as domain or class, and no minimum or maximum number of segments. The address names the Type and stays general. The join says what this artifact does with it and stays specific.
- Why: Types organize reusable functional meaning, and the dotted path lets every level contribute meaning. Keeping the address general and the join specific stops artifact particulars from polluting the Type, and stops a generic Type description from replacing what the artifact actually does.
- How it shows: Any stored address can be walked up to its root one segment at a time.
- Build: An address is one or more segments joined by periods. A segment is lowercase letters and digits, with underscores joining words inside one segment. A Type record exists for every address in use and for every one of its prefixes. The parent of a Type is its address without the last segment; a root Type has no parent. Type records are shared across projects; elements are per project.
- Acceptance:
  1. Storing an element at `code.engine.game.fps` makes `code.engine.game`, `code.engine` and `code` readable as Types, each with the correct parent.
- Relates to: MAP-011, MAP-012, MAP-013, STORE-008.
- Status: the tree and parent rule are confirmed. The exact segment character set is recommended. Shared Type records across projects is recommended here, while STORE-008 keeps Type records in each project store; which holds is open, see open question 12.

### MAP-011 Every prefix of an address is a Type, and inference runs from trunk to leaf

- Requirement: Each prefix of an address is a complete Type in its own right, and meaning narrows from trunk to leaf.
- What this means: `code.engine.game.fps` contains four valid Types. Running inference on them in order, trunk to leaf, goes from general practice for all code, to engines, to game engines, to first-person game engines. The trunk and branch keep the inference in the right domain. The leaf carries most of the specific content. Inheritance runs one way: what holds at a parent holds for every child, and what holds at a child never flows down to its parent. Orientation: the trunk is down and the leaves are up. Something that still holds after its leaf segment is removed belongs lower in the tree, toward the trunk, or in a sibling branch.
- Why: The address itself is a prompting surface. An agent given only an address can produce distinct, useful guidance, and the prefixes give that guidance a place to live once and be inherited by everything above it toward the leaves.
- How it shows: A property attached to the element at `code.engine` applies when reading `code.engine.game.fps`. A property attached to the element at `code.engine.game.fps` does not appear as applying when reading `code.engine`.
- Build: Reading a Type's inherited context walks its prefixes from the trunk up to the Type itself, in that order. The walk never visits children. Attaching and selecting content along this walk is specified in LAYER.
- Acceptance:
  1. A property attached to the element at `code` is returned when reading inherited context at `code.engine.game`; a property attached to the element at `code.engine.game` is not returned as applying when reading inherited context at `code`.
- Relates to: MAP-010, LAYER-005, LAYER-007.
- Status: confirmed. A property at a prefix with no element goes on an element the layer creates there, MAP-022, recommended. Whether other items may attach at a type address that no element holds is open, per LAYER open question 10.

### MAP-012 An address reads as its name when reversed

- Requirement: An address is read as a name by reversing its segments and replacing periods and underscores with spaces, and an element's name_length gives how many trailing segments form its short name.
- What this means: `code.bus.data.event` reads as event data bus code. `data.bill_of_materials` reads as bill of materials data. name_length is the lookback segment count: with name_length 2, `code.engine.game` has the short name game engine. The readable name is presentation. It never replaces the stored address as identity. The namespace address is the name index: an element's proper noun is its address read backward through its name_length, its short name, and an element has no other name, MAP-015. The project's own name for a functionality, its canonical or informal name, is on the join, MAP-020.
- Why: Reading addresses as proper nouns engages the model's existing understanding of types directly, without reasoning. Short names keep references readable.
- How it shows: Every element and Type listing shows the address and its reading, and every element its short name, the element a subtype join holds included. Wherever an element's name is shown, it is its short name.
- Build: reading(address) reverses the segments, replaces underscores with spaces, and joins with spaces. Every root reads as its own name. short_name(address, n) reverses the last n segments, replaces underscores with spaces and joins them. When n is null, zero, or larger than the number of segments, short_name returns reading(address). Readings are computed, never stored as identity. Every read that returns an element, or a subtype join with the element it holds, returns that element's `reading` and `short_name`, computed from its address and name_length.
- Acceptance:
  1. reading of `code.bus.data.event` is event data bus code; short_name of `code.engine.game` with name_length 2 is game engine; short_name with name_length 9 is game engine code.
- Relates to: MAP-010, MAP-015.
- Status: confirmed for the reading rule. The Canonical Intake has two reading examples that disagree on the root: `code.loop.main` reads as main loop program code, and `code.bus.data.event` as event data bus code. The build reads every root as its own name until open question 16 is answered. The edge cases of short_name are recommended. Rich, 2026-09-27: the namespace address is the name index, and an element's proper noun is its address read backward through name_length.

### MAP-013 The namespace rules govern the functional map, and the store does not judge them

- Requirement: The namespace validity rules of the Canonical Intake govern what an intake places in the functional map, not what a knowledge layer creates, and the store records any well-formed address without judging its validity.
- What this means: The rules say an entry must be a functional type, not a genre, medium, encoding, style or purpose; it must be the same thing as its parent or a function within it; it must narrow from trunk to leaf and reverse to a proper name. Those rules are for the agent performing intake. Intake is never gated or judged. Only the resulting map may be graded, and it is refined afterward. The language a project is written in is a medium, so it never appears in an address. A file encoding such as jpg, png or docx never appears in an address under media or document; it may appear under code only where the element is a thing that encodes that file type. A genre or objective, such as platformer, is not a functional type, while fps is, because a first-person view with a targeting reticle is a distinct functionality. These rules govern the intake's functional map only. A knowledge layer is not limited by function: it creates its own namespace objects of any kind the prompt asks for, pure encounter, medium, encoding or anything else, and may link any address at all, LAYER-016.
- Why: A rejecting check loops agents and gates inference. Grading belongs in a later layer that observes the map, not in the write path.
- How it shows: An intake result with a questionable address is stored as written. A later layer or review may flag it.
- Build: The store checks only address form as in MAP-010. It never checks functional validity. Any grading of addresses is a layer written by a module.
- Acceptance:
  1. Storing an element at `media.photo.jpg`, which the rules call invalid, succeeds.
- Relates to: MAP-010, LAYER-016, LAYER-018.
- Status: confirmed.

### MAP-014 Root Types

- Requirement: Every address in the functional map begins with one of the root Types.
- What this means: The Canonical Intake lists the roots as code, document, media, data and stakeholder. Stakeholder holds the parties outside the artifact, such as the VE.
- Why: The roots are the bases every inference starts from, so each root must carry a distinct, well-understood meaning.
- How it shows: The Type tree has one branch per root.
- Build: The root list is data, not code, so a change to it needs no code change. Each entry holds the root name and its reading phrase, MAP-012. The roots are exactly code, document, media, data and stakeholder; there is no exterior, asset or entity root. The store does not refuse an address under another root, per MAP-013.
- Acceptance: None; the list is data and low impact.
- Relates to: MAP-010, MAP-013.
- Status: confirmed. The roots are those of the current Canonical Intake: code, document, media, data and stakeholder. Exterior is no longer a root, and asset and entity are not roots.

### MAP-015 An element is its address in the namespace, and it cannot be moved

- Requirement: An element's identity is its namespace address in its project: the element keeps one stable id for that address, it cannot be moved, and another address is a different element.
- What this means: The address says what kind of thing an element is, and the element is this artifact's realization of it. Rich, 2026-09-27: an element cannot be moved; it is an address in the namespace, and moving it changes its address, so changing an address makes a different element. What is learned about an element, its layer items, memories and properties, is attached to its id, and its id belongs to its address: an element removed and recorded again at the same address is the same element, with every record related to it, STORE-009. When understanding of a functionality improves so that it belongs at another address, the element at the better address is recorded and the functions' joins are moved to it: a join can be moved and stays the same join, MAP-003. Names are lexical handles only; identity is never established by string equality of names.
- Why: Rich, 2026-09-27: the namespace address is the name index and the element is its address, so changing the address changes what the element is. Knowledge built on an element is knowledge about that Type's realization at that address, so it stays with the address. The functions, where the map speaks about the artifact, live in joins, and joins move.
- How it shows: A correction, a knowledge layer's edit or `intake_edit` that gives an element a new address leaves the element at its address and says, in a notice, that an element cannot be moved and that its joins move instead. After a correction moves an element's joins to an element at a better address, the old element keeps its memories and properties, and the joins keep theirs.
- Build: An element record is its element id, its address, its name_length and its role, STORE-009: the namespace address is the name index, and the element holds no name of its own. Its proper noun is its address read through name_length, MAP-012, and the project's own name for a functionality is on the join, MAP-020. Its refs are rows linked to it, STORE-012, and any other field given for it is kept in its extra, STORE-021. Joins, subtype joins and layer items reference element ids, never addresses. Writes that name an element by address resolve it to its id within the project at write time. No write changes an element's address: `address` among the changes of `edit` or `correct` for an element is not applied and is named in a notice, BASE-044 and STORE-034, and the other changes given with it are applied. An element's identity is its namespace address: when a correction layer removes an element, what was attached to it is orphaned, kept and not shown, and when an element is put back at the same address, that same element identity is restored and what was attached shows again, STORE-017.
- Acceptance:
  1. A correction that changes the address of the element at `code.probe` is stored without the address, with a notice naming `address`; after the layer is finished, the element is still read at `code.probe` under its id, with its memory.
  2. A correction layer records an element at `code.probe.echo` and moves to it the join `code.probe` provided: after the finish the join keeps its id and its memory and is read with `code.probe.echo` as its provider, and `code.probe` keeps its own memory.
- Relates to: MAP-003, MAP-012, MAP-016, MAP-020, LAYER-011, STORE-007, STORE-009, STORE-034.
- Status: confirmed. Rich, 2026-09-27: an element cannot be moved, its address is its identity, and a function's join can be moved. This replaces the earlier rule that an element's id survives a change of its address, with relocation taking its attachments along. What an element record holds, Rich 2026-09-27: the namespace address is the name index, and the element was meant to be only its address and name_length; roles stay on the element; the project's name for a functionality goes on the join. This replaces the descriptor item of D78.

### MAP-016 One element per address per project in a map

- Requirement: Within one project's functional map, an address identifies at most one element.
- What this means: The intake traces an element that bears an Operative Purpose as a receiver without creating a duplicate record. The same element may be a receiver in some joins and a provider in others. Any reference to an element, in a join or anywhere else, uses its address, and an address with no element is not a valid reference.
- Why: One record per realized Type keeps every join about that element in one place, so an agent reads the element's receivers, purposes and encounters in one read.
- How it shows: Writing an element at an address that already has one returns the existing element.
- Build: The pair project and address is unique among current elements of a project, the elements subtype joins hold included, MAP-030. A write that names an unknown address as a join's receiver or provider stores the join and creates the element there in the writing layer, with a notice, STORE-026.
- Acceptance:
  1. A second write of an element at an existing address in the same project returns the first element's id and creates no new element.
- Relates to: MAP-015, MAP-031.
- Status: recommended. A subtype join holds an ordinary element, so a subtype and an element never hold one address apart, Rich 2026-09-27; this answers open question 5.

### MAP-017 Every element carries exactly one role

- Requirement: An element carries exactly one role: AUE, VE, DE, SE or NE.
- What this means: AUE marks the artifact under examination. VE marks a party outside the artifact whose purpose drives changes or improvements to it; it is never the person who asked for the intake, the end user, or whoever performs the operation, and it is named at its most specific reusable type level. DE is the element whose loss would stop the artifact being the same type; its function is stated independently of medium, encoding, genre and style. SE, the Substantial Element, is as the Canonical Intake defines it: "An element whose Encounter Function helps the DE serve the VE's OP. It counts as substantial because of what it is meant to contribute to this AUE, even when that contribution is subversive, weak, replaceable, or should be improved." NE is a component, interface or specification that states an essential demand on its environment. Inside the AUE, an element is DE, SE or NE. A VE is an element with role VE and never receives an AUE role. PE is not a role; it is a join's other endpoint. The element a subtype join holds carries DE, SE or NE, on its own element record like every element.
- Why: Roles tell an agent at once how an element bears on the artifact's identity, which is the first thing it needs to orient. A role names what an element is to the artifact: an SE is part of the artifact's substance by what it is meant to contribute, whatever the quality or the direction of that contribution. Supportive would name a helping, secondary part and leave out an element that works poorly or against the DE, which the intake must still map, and it would blur the element's role with the supportive join role the Foundation names, which is a kind of encounter, MAP-022, not a kind of element.
- How it shows: Every element listing shows its role.
- Build: The intake writes exactly one role, from the set above, on every element it creates, the elements its subtype joins hold included: an element's role is on the element record, STORE-009. There may be several VEs. The store records the role as given and does not refuse a missing one, STORE-009 and STORE-026, because the store never judges content; a missing role on an intake element is a defect of that intake, visible to any later layer that grades the map.
- Acceptance: None beyond the intake mapping test in MAP-031.
- Relates to: MAP-020, MAP-030, MAP-031.
- Status: confirmed; roles stay on the element, and SE is the Substantial Element as the Canonical Intake defines it, 2026-09-27. Whether one VE is recorded as primary is open, see open question 6. STORE-009 allows an element with no role; whether an element created by a layer other than the intake must carry one is open, see open question 13. How an element records its role when one project holds several AUEs and the element plays a different role for each is open, question 19, D87.

---

### MAP-020 A join records one encounter in full

- Requirement: A join records its type, its receiver or, for a subtype join, the parent join it sits in, its provider, optional name, purpose, function, ef, relation, verb, observation, optional non_goal and optional refs.
- What this means:
  - type: the kind of join. Intake writes type purpose for a join held by its receiver, and type subtype for a subtype join, MAP-030. Modules may define other join types, and unknown valid content survives reads, edits, copies and export.
  - receiver: the element that owns the join and holds the purpose. A subtype join has none; its parent join holds it.
  - parent: on a subtype join, the purpose join it sits in, MAP-030; on every other join, none.
  - provider: the element whose function serves the purpose; on a subtype join, the element it holds.
  - name: the project's own name for the functionality the join names, its canonical name in the project's official terminology or an informal name, where the project has one. The join is where the map speaks about the artifact itself, so the name is on the join and never on an element, whose only name is its address read through name_length, MAP-012. A subtype join carries its own, MAP-030.
  - purpose: the active Operative Purpose statement, the why.
  - function: the provider's Encounter Function for this specific encounter, the how.
  - ef: the Encounter Function's word, one of two: Function if it is the encounter of a functionality, or Encounter if it is the functionality of the encounter. A subtype join carries its own, MAP-030.
  - relation: an active-voice descriptive fragment that starts directly with a third-person singular present-tense verb ending in -s or -es. Its subject follows ef: the provider when ef is Function; when ef is Encounter, the Vested Entity on a top-level join and the Receiving Entity in a subtype join, since the Vested Entity holds only top-level joins.
  - verb: the verb of the relation, a third-person singular present-tense active verb ending in -s or -es, as the intake agent infers it. It is the agent's word, never a set list. A subtype join carries its own, MAP-030.
  - observation: the actual real-world condition, format, layout or limitations of what is there.
  - non_goal: an outcome the receiver does not seek, recorded only where it materially clarifies the purpose.
  - refs: type-specific or artifact-specific references or logic, only where needed.

  An encounter function states a function. A language, medium or encoding never goes into an encounter. A join speaks about this artifact. Its purpose and function state what this artifact actually does in its own particulars. Where the artifact represents something, the join describes the function of that representation within the artifact, not the real-world function of the thing represented.

  Voice: the fields are written with third-person singular present-tense active verbs, ending in -s or -es, so each reads as a sentence when printed after the element's name, its proper noun read through name_length, MAP-012, and the fields read together when concatenated. The intake agent also writes, for each element, a concise statement that continues from its name. The relation and the verb follow this voice, as the Canonical Intake states them. Which other fields follow it, which element's name each field continues from, and where an element's statement is kept, since an element holds only its address, name_length and role, MAP-015, are open, D90.
- Why: Functions live in joins, and joins speak to the artifact. Keeping each field separate lets an agent ask one question at a time, who, why, how, what is actually there, and get a direct answer. The project's own name for a functionality is on the join because the address is the element's name as a reusable Type, while the join is where the map speaks about this artifact: the name belongs to the encounter, and on the element it would tie a reusable Type to one project's vocabulary. Fields in one voice read as plain statements about the element they follow, the way an address reads as a proper noun, MAP-012, so a join printed after an element's name is taken in as sentences about that element rather than parsed.
- How it shows: Reading a join returns every field it was written with, each on its own.
- Build: Each field is its own column. Nothing is packed into a shared text or JSON field except extension content of module-defined join types, which is stored and returned intact. `type` is `purpose` for every join the intake writes held by its receiver and `subtype` for every subtype join; a module-defined type is any other name in the address form of MAP-010, declared by the module that writes it. purpose, function, relation and observation must be present, not null, on purpose joins; an empty string is stored as given, STORE-026. `ef` holds only `Function` or `Encounter`; any other value is kept in the join's `extra` and named in a notice, and a missing one is named, BASE-044. `verb` is stored as given, and a missing one is named. non_goal is nullable. `name` is stored as given and is nullable. refs follow MAP-021.
- Acceptance:
  1. A join written with every field, including a name, a non_goal and two refs, reads back with each field equal to what was written.
  2. A join of a module-defined type with extension content survives export and import unchanged.
  3. A join or subtype join written with an `ef` of `Both` reads back with no `ef`, the word kept in its `extra` and a notice naming `ef`; a correction that changes another field keeps the `ef`.
- Relates to: MAP-003, MAP-012, MAP-015, MAP-021, MAP-022, MAP-030, MAP-040, STORE-010, STORE-021.
- Status: confirmed. `verb` as its own field, the relation's subject, and `ef` as a choice between the two words, never freeform inference, 2026-09-26; the verb changes the relation's grammar rules and not the intake's semantics. The subtype join as a join of type subtype held in its parent join, the relation's subject in a subtype join, and `name` on the join, the purpose join and the subtype join alike, 2026-09-27. The voice of the fields and each element's statement are confirmed as design, 2026-09-26 and 2026-09-27; their extent is open, D90, and the Canonical Intake's wording for them is D99.

### MAP-021 Refs are an ordered key and value list

- Requirement: Elements and joins, subtype joins included, carry refs as an ordered list of key and value pairs.
- What this means: refs hold references such as key path with a relative file path, or other type-specific keys. The same key may appear more than once, for example several member paths. A file name or path is legal in a ref and never legal as a namespace address.
- Why: One uniform shape serves any artifact type without a schema per type, and repeated keys let a join list every member of a grouped Artifact Type.
- How it shows: A join grouping three files lists three path refs in the order written.
- Build: Each ref is its own record with owner, position, key and value, indexed by owner and by key and value, so an agent can find every element or join citing a given path directly.
- Acceptance:
  1. Looking up key path with a given file returns every join whose refs cite it, including subtype joins inside joins.
- Relates to: MAP-020, MAP-030, STORE-012, STORE-025.
- Status: confirmed.

### MAP-022 Every encounter is a function or a property

- Requirement: Every encounter is either a function, carried by a join, or a property, carried by a transitive property record attached to an element; properties never have joins.
- What this means: Both are encounters. A function encounter is a join: a receiver's purpose served by a provider's function, MAP-020. A join is always a function encounter; there is no property join and no join kind. Supportive is a kind of encounter function, not a kind of element: a Substantial Element's encounter is a function, carried by a join. A property is its own record: the element it is attached to, its value, and the layer that owns it, STORE-039. A property attaches only to an element, never to a bare namespace address or a join, a subtype join included. Its link to the element can be moved, since it only links the property to an element, STORE-034. When a property belongs at a namespace prefix where the project has no element, such as a practice for `code` in general, the knowledge layer creates an element at that prefix, as a layer may create a new element, and attaches the property to it. The namespace tree itself links that element to every element toward the leaves from it, so no join is needed, and its properties apply toward the leaves from there. A property is transitive along the namespace from its element's address, LAYER-005: from the address where it is linked, inference goes toward the trunk and toward the leaves, applying toward the leaves and visible toward the trunk. So Bash attached as a property to the installer element applies at every address toward the leaves from the installer and is visible at `code`, and a property linked near the trunk applies to every branch after it. Knowledge layers work the same way, LAYER-016: a knowledge item is either a property, transitive and attached to an element, including an element the knowledge layer created and linked to the metaform, or a function, a join. Hard dependency, property and supportive are not join roles. How a property is recorded is open, D88: this record and STORE-039 hold it as a value attached to an element; the design also speaks of property joins, and of an element of any kind linked to the node where it belongs, the link marking it as a property, LAYER-020.
- Why: A function stays with the one receiver it serves, so it belongs in that receiver's join. A property describes what something is, so it flows along the namespace to everything toward the leaves from where it is linked and shows toward the trunk; giving it a join would tie it to one receiver and stop it flowing. Two kinds of encounter, one carried by joins and one by properties, keep one model for the map and every knowledge layer.
- How it shows: A property linked at an address appears as applying at every address toward the leaves from it and as visible at the trunk; a join appears only as its receiver's join.
- Build: Joins are stored as in STORE-010, with no kind column. Properties are stored as in STORE-039 and read through STORE-035: the applying set at an address holds the properties attached to the elements at it and at every prefix; the visible set holds the properties attached to elements toward the leaves from it. The intake produces no properties; properties come from knowledge layers, MAP-040. Until the intake text emits them, the intake tools record only elements, joins and subtype joins, and properties come from knowledge layers.
- Acceptance:
  - With Bash attached as a property to the element at `code.installer`: a read at `code.installer.script` receives Bash as applying; a read at `code` shows Bash as visible and not applying; a read at `code.engine` does not receive it.
  - A join from `code.installer` to a provider is received only as that receiver's join and at no other address.
  - No write path accepts a join marked as a property.
- Relates to: MAP-020, MAP-011, LAYER-005, LAYER-016, LAYER-020, STORE-010, STORE-034, STORE-035, STORE-039.
- Status: creating an element at a prefix to hold a property there, linked by the namespace tree with no join, is recommended. Confirmed, 2026-09-25, that every encounter is a function or a property, that properties are transitive records attached only to elements with no joins, that supportive is a function, and the direction of transitivity above. Confirmed, 2026-09-27, that a property's link can be moved. The intake produces no properties; they come from knowledge layers. Whether hard dependency survives in any form is open, open question 17. How a property is recorded is open, question 21, D88.

### MAP-030 Annealing places an absorbed element in its parent's join as a subtype join

- Requirement: Annealing places an absorbed element inside its parent functionality's purpose join as a subtype join, a join of type subtype held inside that purpose join and naming the element it holds, with its own encounter function and never a purpose of its own; the element itself does not move.
- What this means: Annealing combines parts that share a join into a bigger functionality that describes them all. Each part serves the same receiver's purpose through the same join. The bigger functionality becomes the provider of a combined encounter, and each part hangs under that combined encounter in a subtype join, keeping its own encounter function. Two probes absorbed by a failsafe, serving a daemon's purpose of catching a dead gateway, are held by subtype joins in the failsafe's join. Rich, 2026-09-27: an element always appears as one element record; annealing places it in its parent's join as a subtype join, and the element itself does not move. The part stays an ordinary element at its own address, with its name_length, role and refs, and the subtype join places it: it carries its function, ef, relation, verb, observation, an optional non_goal, its name and its refs, and no purpose.

  A subtype join has no purpose of its own. A part that holds its own purpose is not sharing the same join: it is its own receiver with its own join, so it stays an element of the outer map. A command line and a status page that each need node state from a control API each hold their own purpose, so each is an element with its own join to the control API.

  Absorbing is legal only when the parts share that join and the combined encounter covers each part's encounter function. Combining never optimizes a functionality away.

  Annealing is a join move, MAP-003: the join where the part provides becomes the subtype join inside the parent's join, the same join with its id, its fields, its history and whatever is attached to it. Its purpose, which the parent's join now carries, is kept in its extra.
- Why: Annealing keeps the root map minimal, coarse and shallow without discarding any functionality. A subtype join exists only because the part shares that join, so the join is where it lives. A purpose is what gives a part its own join, so a part with a purpose cannot live inside another's join. The element stays one record because an element is its address and cannot be moved, MAP-015: absorbing it changes where its function is placed, not what it is.
- How it shows: Reading a join returns its purpose and combined function and, beneath them, each subtype join with its own function and the element it holds. `intake_absorb join=<the probe's join> into=<the failsafe's join>` makes the probe's join a subtype join of the failsafe's join, with the same join id.
- Build: A subtype join is a `joins` row, STORE-010 and STORE-011, of type `subtype`, whose `parent` is the purpose join it sits in and whose `provider` is the element it holds, an ordinary element record, STORE-009. It has no receiver of its own, since its parent join's receiver owns it, and no purpose: a purpose given for it is kept in its `extra`. Its own fields are its name, the subtype join's name for the functionality, MAP-020, function, ef, relation, verb, observation, non_goal and refs. The element's address, name_length and role are on the element's own record. The parent join holds the purpose and the combined function. Coverage is the intake agent's judgment and is never checked by the store. Absorbing is a change of the join's `parent`, STORE-034: the join becomes of type `subtype`, its receiver is taken off, its purpose goes to its `extra`, and every other field is kept; any other join that still names the element is listed in a notice and left as it is, BASE-044.
- Acceptance:
  1. A join with two subtype joins reads back with the purpose and combined function on the join and, under it, each subtype join's own function, relation and observation with the address, name_length and role of the element it holds.
  2. A subtype join given a purpose is stored as given: the purpose is kept in its `extra`, and the result carries a notice naming it, BASE-044.
  3. Absorbing the join a part provides into its parent's purpose join keeps the join's id, name, function, ef, relation, verb, observation, non_goal, refs and a memory attached to it, puts its purpose in its `extra`, leaves the part's element record unchanged at its address, and names in a notice another join that still names the part.
- Relates to: MAP-003, MAP-015, MAP-031, MAP-032, MAP-040, STORE-010, STORE-011, STORE-034.
- Status: confirmed. Rich, 2026-09-27: an element always appears as one element record, annealing places it in its parent's join as a subtype join and the element itself does not move, and a function's join can be moved. The subtype join as a join of type `subtype` with an optional non_goal and no provider field of its own in the intake tools, the store's shape, and absorbing as one call that takes two join ids are recommended; the Canonical Intake's schema still shows a provider beside the nested element and no type or non_goal, which changes only with Rich's wording, MAP-040.

### MAP-031 An element held only by subtype joins is never a root and never a node of the outer map

- Requirement: A subtype join is never an edge of the outer map, and an element whose only joins are subtype joins is not a root and is not drawn as a node of the outer map; both are reached through the join that holds them.
- What this means: The absorbed element is not mapped to the external graph, Canonical Intake step 11. It keeps its own address and record, its encounter function stays in its subtype join, and layers and memory attach to the element directly, by its element id, and to its subtype join, by its join id. An element that also receives or provides a join of its own is a node of the outer map like any other, because that join places it there.
- Why: Keeping subtype joins inside their join is what keeps the root map minimal. Keeping the element one addressable record is what lets memory and layers still reach the specific part.
- How it shows: The roots and the graph reads do not show an element held only by subtype joins. Reading its address returns the element with the subtype join that holds it and that join's parent join.
- Build: A subtype join's current row is in `current_subtypes`, never in `current_joins`, STORE-011, so every read of the element graph, the joins an element receives or provides, identity and the joins the outer map draws, cannot return it. An element held only by subtype joins is the end of no current join, so the element graph never reaches it; the reads that list elements by address or role for the outer map, `graph`, `layer_graph` and `roots`, STORE-025, leave it out through one check, `held_only`: the element is held by a current subtype join and is the receiver or provider of no current join. Reading by its address, `where`, returns the element, the subtype join that holds it and its parent join.
- Acceptance:
  1. After storing a map with subtype joins, the roots and graph reads contain no element held only by subtype joins, and reading its address returns it with its subtype join and its parent join's id, receiver and provider.
  2. A layer item attached to the element a subtype join holds is returned when reading that element, and one attached to the subtype join when reading that join.
  3. An element held by a subtype join that is also the receiver of a join of its own is in the graph read.
- Relates to: MAP-030, LAYER-003, STORE-011, STORE-025.
- Status: confirmed that the absorbed element is not mapped to the external graph and that an element whose only joins are subtype joins is not a root and not a node of the outer map, Rich 2026-09-27. The `held_only` check is recommended.

### MAP-032 Subtype nesting and ownership limits

- Requirement: What a subtype join may hold and where it may sit are settled before storage fixes them.
- What this means: Three cases: whether the element a subtype join holds may be a join end of its own; whether one element may be held by subtype joins in two different joins; whether a subtype join may itself hold subtype joins.
- Why: Each answer changes what the store must allow, and guessing would bake a wrong rule into the schema.
- How it shows: An element held by a subtype join that receives a join of its own is also a node of the outer map. An element held by two subtype joins is stored, with a notice naming the other. A subtype join is placed only inside a join held by a receiver.
- Build: A subtype join's parent is a join held by a receiver. `add_subtype`, or a change of a join's `parent`, that names as the parent a subtype join, no join, or the join itself cannot be read, STORE-026: nothing is written. So a subtype join holds no subtype joins, D5, and the parent chain is one step and never a cycle, MAP-002. A join absorbed while it holds subtype joins passes them to its new parent, each named in a notice, since a subtype's joins lift to the parent when it is annealed, D3. The element a subtype join holds may be a join end: its joins lift to the parent by the agent's own moves, D3, and until they do it is a node of the outer map, MAP-031. An element already held by another current subtype join is stored as given with a notice naming that subtype join, since a part serving two joins is its own element, D4.
- Acceptance:
  1. A subtype join added inside a subtype join is an error naming a join held by a receiver, and nothing is written.
  2. An element held by two subtype joins is stored, and the second call's notice names the first.
  3. Absorbing a join that holds a subtype join leaves that subtype join inside the new parent, named in a notice.
- Relates to: MAP-030, MAP-031, STORE-011.
- Status: D3, D4 and D5 as answered, carried into the subtype join, which answers open questions 3, 4 and 8. Passing the subtype joins of an absorbed join to its new parent is recommended, from D3 and D5.

---

### MAP-040 An intake result becomes map records

- Requirement: An intake is recorded through the intake module's tools one object per call, as it is reasoned, and stored as elements, joins, subtype joins and refs in one intake layer, with nothing lost.
- What this means: The intake's instructions are delivered to the performing agent by name. The agent records the map as it works the method: it starts the intake, records each element, join and subtype join in its own call as soon as it is reasoned, and, once everything is recorded, performs the proofing pass of step 12: it reads the recorded map back, whole or one receiver at a time, checks it against the artifact and the intake document, corrects it, anneals it and completes it, then finishes the intake, BASE-039. The tools never parse the intake's XML: each takes one object's fields, named as in the intake's response schema, which is the metaform's general data pattern: elements, joins held by receivers with purpose and function, subtype joins inside their parent join with their own function and no purpose, and refs. The intake text can change as long as its data still follows that pattern, with no change to the tools. The intake produces no properties; properties come from knowledge layers, MAP-022. An intake's result need not be the same across models or runs: it is collected once, when the project is taken in, its quality follows the model and what the model knows of the project, and blind spot analysis over it, LAYER-014, is its quality check, never repeated runs.
- Why: The map is only useful if everything the intake agent recorded can be read back exactly, and the intake agent's inference is the expensive part. A schema owned by the tools keeps storage stable while the intake text improves. An intake is long, so the agent records the map as it builds it and the web GUI shows each object as it arrives; once everything is recorded, the agent proofs it. Recording as it goes improves the result and lets any model, and agents with smaller context windows, perform the same intake, since no agent has to hold the whole map in its head: the system helps the agent build the metaform. For the same reason the intake does not depend on the size of the agent's context: the agent reads back one receiver's joins at a time and anneals with one call per join. Running the intake again to make its result stable would spend that expensive inference again on what blind spot analysis checks from outside the intake agent's frame.
- How it shows: While the intake is recorded, the web GUI draws each object as it arrives, VIEW-005, and no context read sees the intake. After the intake finishes, every element, join, subtype join and ref recorded is readable from the store.
- Build: `intake_start` opens one building intake layer with its provenance record, LAYER-010; each `intake_element`, `intake_join` and `intake_subtype` call writes one object into it, STORE-024; `intake_absorb` makes a recorded join a subtype join inside its parent's purpose join, MAP-030; `intake_show` reads it back, whole through the store read `layer_graph`, STORE-025, or one receiver's joins and what they hold; `intake_edit` and `intake_remove` change it in place while it is building, STORE-032; `intake_finish` marks it ready, and from then on it changes only through correction layers, STORE-017. Every tool names an object's id by the key its recording call returned: `element_id`, `join_id`, and for a subtype join `join_id`, since a subtype join is a join, with `parent` for the join it sits in. The element's address is `namespace_address` in every intake tool, as in the Canonical Intake. The current intake schema, `specifications/Canonical_Intake.xml`, maps to the tools and the store as follows:

  | Intake XML | Tool field | Store |
  |---|---|---|
  | `result@id` | `intake_start` `id` | `layers.result_id` of the intake layer |
  | `element@namespace_address` | `intake_element` `namespace_address` | `elements.address` with a new identity id, STORE-009; the address row in `types`, STORE-008 |
  | `element/name` text | `intake_element` `name` | not held by an element: kept in the element's `extra` under `name`, with a notice that the project's name for a functionality goes on the join, BASE-039 |
  | `element@name_length` | `intake_element` `name_length` | `elements.name_length`, STORE-009 |
  | `element@role` AUE, VE, DE, SE, NE | `intake_element` `role` | `elements.role`, STORE-009 |
  | none in the current schema for a root element | `intake_element` `refs` | `refs` rows owned by the element's row, STORE-012 |
  | `join`, held inside its receiving element's `joins` | `intake_join`, `receiver` the enclosing element's address | `joins` row, STORE-010 |
  | `join@type`, always `purpose` | `intake_join` `type`, `purpose` when left out | `joins.type` |
  | `join@provider` | `intake_join` `provider` | `joins.provider`, the provider's identity id resolved by address |
  | `join@purpose`, `@function`, `@ef`, `@relation`, `@verb`, `@observation`, `@non_goal` | `intake_join`, same names | same-named `joins` columns, MAP-020 |
  | none in the current schema | `intake_join` `name` | `joins.name`, MAP-020 |
  | `join/refs/ref@key`, `@value` | `intake_join` `refs` | `refs` rows owned by the join, in order, STORE-012 |
  | nested `join` inside a `join` | `intake_subtype`, `into` the parent join's id | `joins` row of type `subtype` with `parent` that join, STORE-011 |
  | nested `join@function`, `@ef`, `@relation`, `@verb`, `@observation` | `intake_subtype`, same names | same-named columns of the subtype join's row |
  | none in the current schema | `intake_subtype` `non_goal` | `joins.non_goal` of the subtype join |
  | the nested `element@namespace_address`; the nested `join@provider` repeats it | `intake_subtype` `namespace_address` | the element at that address, recorded when there is none, STORE-009, named by the subtype join's `provider` |
  | nested `element@name_length`, `@role` DE, SE, NE | `intake_subtype` `name_length`, `role` | the element's own `name_length` and `role`, STORE-009 |
  | nested `element/name` | `intake_subtype` `name` | `joins.name` of the subtype join, MAP-020 |
  | nested `element/refs/ref` | `intake_subtype` `refs` | `refs` rows owned by the subtype join, in order |
  | step 9 and step 12, anneal | `intake_absorb`, `join` the join where the element provides, `into` the parent's purpose join | that `joins` row, made of type `subtype` with `parent` set, STORE-034 |

  Built this way the structure follows the pattern that makes it acyclic: each join is held by its receiver and runs one way to its provider, a subtype join sits inside its one join with no purpose, and a relationship in the other direction is its own join with its own purpose, MAP-020 and MAP-030. Only the element-to-element view, which ignores purposes, can show a cycle. A join whose provider is its own receiver is stored as given with a notice, D82.

  When the result has no element with role AUE, none is created. The artifact is still recorded by the project's target, MAP-041.

  An element is its address, name_length and role, STORE-009, and the project's own name for a functionality is on the join, MAP-020, the purpose join and the subtype join alike. The Canonical Intake's schema shows a `<name/>` inside each element; until its wording changes, D99, an agent following it sends the element's name with `intake_element`, which keeps it in the element's `extra` and says in a notice where the name goes, BASE-044; the nested element's name it sends with `intake_subtype` is the subtype join's name, where the name belongs.

  The Canonical Intake's response protocol tells the agent to remove absorbed subparts recorded as root elements and keep them only as subtype joins. The element stays one record, so an absorbed element held only by subtype joins is not a root, MAP-031, with nothing removed. An agent that removes it anyway leaves its subtype join orphaned, and `intake_remove` names that join in its notice, STORE-032. The protocol's wording is D99.
- Acceptance:
  1. Recording a real intake result, such as a real project's map, then reading the project back yields the same set of root elements with their name lengths and roles, joins with every field, subtype joins with their names and functions and the elements they hold, and refs in order.
  2. No element held only by subtype joins in the result appears as a root element after storing.
- Relates to: MAP-015, MAP-020, MAP-021, MAP-030, MAP-031, MAP-047, LAYER-001, LAYER-010, LAYER-014, STORE-009, STORE-013, STORE-024, BASE-039, MCP-009.
- Status: confirmed, 2026-09-26: recorded one object per call as it is reasoned, with any model, read back and proofed in step 12, then finished; the tools' own fields; the mapping of root elements, joins, nested subtype joins and refs. Confirmed, 2026-09-27: the element is its address, name_length and role, and names go on joins; the element stays one record and annealing places it in its parent's join as a subtype join; the intake does not depend on the size of the agent's context. Confirmed, 2026-09-12: an intake's result need not be the same across models or runs, and blind spot analysis is its quality check. The Canonical Intake's wording where it differs from this shape is D99. The field name `namespace_address` in every intake tool, `into` for the parent join, the ids under the keys their recording calls return, `intake_absorb`, the receiver-scoped `intake_show`, a subtype join's refs on the subtype join, keeping an element's name in its `extra` until the Canonical Intake's text changes, and the handling of a missing AUE, are recommended.

### MAP-041 Metaform works on any artifact, and the artifact's boundary stays explicit

- Requirement: Metaform maps software and non-software artifacts alike, and every project records exactly which artifact it maps and where that artifact's boundary is.
- What this means: The artifact can be a codebase, one project inside a repository that holds several, a document, a folder of photographs, a design, a contract, a story, or any other source material. Nothing in the chassis, the store or the map assumes the artifact is code. The root Types cover every kind of artifact, and the map records function, not medium. Each project names its artifact the way the Canonical Intake's target does: a path, a URL, an artifact name in the working folder, inline content, or inferred. That target and its boundary are part of the project record, so every reader knows what the map is about and what lies outside it.
- Why: Metaform captures what a thing is for, and every artifact has receivers, purposes and encounters, whatever its medium. An agent working from a map must know which artifact the map describes and where it stops, or it reasons about the wrong material.
- How it shows: Registering a folder of photographs and mapping it works the same way as registering a repository. `metaform` status and every read of the project show the artifact's target type and value.
- Build: The project record holds the target type, one of path, url, artifact, inline or inferred, and the target value, alongside the project id. A project that maps one project inside a larger repository records that project's own folder as its path, not the repository root. No chassis code branches on whether the artifact is software.
- Acceptance:
  1. A project registered on a folder that holds only images accepts an intake whose elements sit under the media root, and reads them back.
  2. The project record returned by status and by the read operations includes the target type and value.
- Relates to: MAP-014, MAP-040, STORE-002, STORE-003, MCP-009.
- Status: confirmed.

### MAP-042 Elements and entities are distinct

- Requirement: An entity is an element that may contain elements, not every element is an entity, and an entity's Type need not be its Defining Element's Type.
- What this means: The artifact under examination is an entity: it contains the elements the intake finds in it. Its Defining Element is one of those elements, the one whose loss would stop the artifact being the same Type. The artifact and its Defining Element are two records with two Types. An agentic delivery framework as a whole and the delivery workflow that defines it are an example: the whole is one Type, the defining part another. A Vested Entity outside the artifact is also an entity in this sense, a party that holds purposes. An ordinary element such as a supportive script is not an entity.
- Why: The whole and the part that defines it answer different questions. Collapsing them would force the artifact's Type to equal its Defining Element's Type, which loses either the functional type of the whole or the specific function of the part.
- How it shows: A mapped project holds one element with the AUE role and, separately, one with the DE role, each with its own address. Reading the AUE element does not return the DE's address as its own.
- Build: The AUE is stored as an element with role AUE and its own address and identity when the intake result names one. When it names none, no AUE element is created, MAP-040, and the project's target records the artifact. The DE is a separate element with role DE. Elements carry no flag of their own saying entity or not; being an entity follows from the role, AUE or VE. Which elements belong to which AUE, when a project holds more than one AUE, is open.
- Acceptance:
  1. An intake result whose AUE and DE have different addresses is stored as two elements, and both addresses read back unchanged.
- Relates to: MAP-015, MAP-017, MAP-040, STORE-009.
- Status: confirmed for the distinction; open for recording which elements belong to each AUE when a project holds several, D51, and for how an element records its role for each of several AUEs, D87.

### MAP-043 Reasoning that needs the artifact receives the artifact

- Requirement: Any reasoning that depends on source evidence receives the actual evidence, not just names or generic Type descriptions, and the source's identity and project context travel with it.
- What this means: The map records where each element lives in the artifact, through refs such as a path. A worker that must judge the artifact itself, such as an intake agent or a sighted critic, is given the project's target and the refs, and reads the real material. A Type's universal description is never a stand-in for looking at the artifact. Metaform-only blind spot analysis is the one deliberate exception: its role is to reason from the map alone, so it receives the map and not the artifact, and its layer's provenance records that it was blinded.
- Why: A map built or checked from names alone repeats whatever the names suggest, and the errors then look like the artifact's own. Keeping the source identity and the project with the evidence means every conclusion can be traced back to the material it came from.
- How it shows: The intake instructions a subagent reads name the project's target. Reading an element or a join returns its refs, so an agent can open the exact files or passages behind it.
- Build: Every element and join read returns its refs in order. The intake instructions served by name carry the project's target, filled into the intake text's `<target>` element, BASE-039. The project id is filled into the text only where the text holds a `{project_id}` placeholder; otherwise the intake tools record into the folder's project, or the project named by their optional project argument, MCP-025. A workflow that gives a worker source evidence passes refs and the target, never a summary in their place. A blinded role receives map reads only, and its provenance record sets blinded to true.
- Acceptance:
  1. Reading a join returns its path refs exactly as written.
  2. The served intake instructions for a registered project contain that project's target type and value in the `<target>` element.
  3. The intake tools called with a project argument record into that project, whatever the folder.
- Relates to: MAP-021, MAP-041, LAYER-010, LAYER-015, MCP-009, STORE-025.
- Status: confirmed.

### MAP-044 A new element joins the metaform on either side of a join

- Requirement: An element or entity that a layer adds joins the metaform through a join on either side, under the same rules as every join: as a receiver it owns the join it holds, and as a provider its join is held by the existing receiving element that names it.
- What this means: A layer can add a new element or entity anywhere the design is open. Two cases, one rule. As a receiver, the new element holds its own purpose and owns the join it makes to an existing provider, using a function the metaform already has, under whatever name fits. As a provider, the new element serves the purpose of an existing element: the join is made in that existing receiving element, naming the new element as its provider. Either end can be the new one, and nothing else about the join differs from any other join, MAP-002, MAP-003. Functions are not transitive: a new element carrying a function or a purpose reaches the metaform only through its join, never through the namespace tree. The namespace-tree link belongs only to an element a layer creates at a prefix to hold properties, MAP-022.
- Why: A function exists only because it serves a receiver's purpose, and a purpose exists only because something receives it. A join is the one way either connects to the metaform, and the receiver always owns it, so one rule covers every new element, whichever end it takes.
- How it shows: A layer adds a new receiver that uses an existing probe: the join appears under the new receiver, naming the probe as provider. A layer adds a new provider for an existing gateway's purpose: the join appears in the gateway's joins, naming the new element as provider. Both reads show the adding layer's name.
- Build: The new element is written with `add_element` in the adding layer and its join with `add_join` in the same layer, STORE-024. `add_join` takes receiver and provider as element ids; either may be new, and the join is stored with its receiver as owner, STORE-010. The join's layer is the adding layer, so it extends the metaform only where that layer is toggled on, LAYER-016.
- Acceptance:
  - A layer adds a new element as receiver with a join to an existing provider: the receiver's `joins` read returns the join, and the provider's `identity` read in context returns it while the layer is on and does not while it is off.
  - A layer adds a new element as provider for an existing receiver: the join is stored with the existing element as receiver and is returned by that receiver's `joins` read with the adding layer's name.
  - A new element with a function and no join does not appear in any in-context read of an element of the metaform or of its namespace prefixes.
- Relates to: MAP-002, MAP-003, MAP-020, MAP-022, LAYER-003, LAYER-016, STORE-010, STORE-024.
- Status: confirmed.

### MAP-045 A project can have more than one metaform

- Requirement: A project can hold more than one metaform, each the container of one intake map, its correction stack and every layer built on it, and exactly one of them is the project's active metaform.
- What this means: A metaform is the intake map of an artifact together with the correction layers stacked on it and every knowledge and memory layer attached to it. Every layer belongs to exactly one metaform, the correction stack included. A project starts with one metaform. Starting over is creating a new metaform for the same project: it starts empty, with no intake map, no corrections and no layers, and the old metaform is kept whole with all its layers. One metaform is selected as the project's active metaform, and every read, write, status line and agent instruction for the project uses the active one. Selecting an older metaform again makes it active again exactly as it was left.
- Why: A map can be redone from scratch, for example after the intake procedure improves, without losing the work built on the earlier one. Keeping each metaform whole, with its own layers and corrections, means nothing from one can leak into or corrupt the other, and switching back is always possible.
- How it shows: `metaform add metaform fresh` in a project with an intake creates an empty metaform and makes it active; status then shows the no-intake notice, because the active metaform has no intake. `metaform list metaforms` shows both, marking the active one. `metaform activate metaform main` switches back, and every layer of `main` reads exactly as before.
- Build: The metaform records, the one store per metaform, and the active selection are STORE-041. The verbs are CLI-031: `add metaform`, `list metaforms` and `activate metaform`, and the map module's tools, BASE-038. `has_intake()` answers for the active metaform, STORE-032.
- Acceptance:
  1. After `add metaform fresh`, the node read of an element that existed in the old metaform returns not found, and status shows the no-intake notice.
  2. After `activate metaform main`, every read returns exactly what it returned before `fresh` was added.
- Relates to: MAP-040, LAYER-001, LAYER-011, STORE-003, STORE-041, CLI-031, BASE-038.
- Status: confirmed for more than one metaform per project, every layer and the correction stack belonging to one metaform, one active metaform per project, starting over as a new empty metaform, and the old one kept and selectable. The storage and verbs are recommended.

### MAP-046 The condition of an object is a work record, apart from the map
- Requirement: The map holds the intended shape of the project; the condition of an element or a join, a subtype join included, `tbd`, `broken` or `cruft`, and `in-progress` or `fixing` once an agent has taken its task, is a work record attached to it and kept apart from the map, with a note, a task, and its resolution once done.
- What this means: The intake maps the project from its specifications and decisions as well as its code, so the map is the whole intended project: it says what is built and what is not built yet, and the intake layer holds only functional shape, never the condition of its objects. The condition is a work record, STORE-042. `tbd`, to be done or determined, replaces `missing`: the object is in the specs or decisions and not built yet, and its task says whether it needs building or deciding. `broken` is something in the artifact that is broken, not working, not connected or orphaned. `cruft` is code, and only code: code that has been surpassed and is left in the codebase, disabled or unused, together with any conversion written to carry the surpassed thing forward. It names nothing else. A document, a note, a specification, an example, a prompt, an intake, working data and a quality standard are never cruft, whether or not they match the code as it stands. Metaform has no legacy: it has not been given to anyone, so nothing in it is kept for the sake of an earlier version, and code that converts from one is itself cruft. The note says what and where; the task says what it needs. An agent that takes a record's task says so with `map work op=take`: a `tbd` record becomes `in-progress`, a `broken` one `fixing`, and the record no longer waits to be taken; a record taken or done cannot be taken again, so two agents never hold one task. A record is open until its task is done, and then it is done with its resolution kept beside it, never erased. It carries `held`, which keeps it waiting until agents are assigned or take it, MAP-049, and `reviewed`, set once it has been checked for correctness before it is fired off. The intake agent writes work records as it maps, because it reads every file and decision and sees the difference between the functionality that should exist and the functionality that does. A critic that sees an issue and knows what it needs writes the task as well as the finding, and sets held, so the tasks line up to be worked until the queue is clear. An agent that finds something wrong writes a `broken` record with the details of the problem, which makes the node flash red, VIEW-005. Any agent can write one, at any time, after the intake has finished too. Changing a work record is work proceeding: it never changes the map and is never a correction.
- Why cruft is code only: `cruft` is the one condition whose task ends in removal, so what it may name has to be narrow. An agent judges by the code it reads, and whatever does not match that code looks old to it; code that was surpassed is old, but a note about design that is not built yet only looks old, and removing it removes the reasoning the design came from. Cruft appears when something was built wrong and then kept: the wrong thing is called legacy and a conversion to the new thing is written, so the codebase carries both. With no users there is no one to convert for, so the name legacy protects nothing.
- Why a taken task is its own condition: a part someone is building and a part no one has started look the same to the next agent unless the record says which, and that agent would start the same work again. Saying it on the record is also what lets the map show where work is happening now.
- Why: The difference between what should exist and what does is as valuable as the map, and it belongs where it applies; but it is condition, not shape. Kept apart, the map stays the intended project while records come and go, an agent reading an object sees its condition there, and the records can be listed to line up and work through the tasks. The red node is what shows a person a problem the moment they look at the map.
- How it shows: An intake of a repository with a disabled legacy module records `cruft` on that module's element with the note `disabled since the 2.0 rewrite` and the task `remove the module and its tests`. `metaform map work condition=cruft` lists it. In the web GUI a node with an open `tbd` record keeps its color and opacity and has a bloom around it, which goes when its task is done; a node with an open `broken` record flashes red until it is resolved; an object with an open `cruft` record is drawn in the cruft color, which no layer or role uses, and pulses, VIEW-005; the panel lists the node's records, VIEW-005 and VIEW-009.
- Build: The `work` table and the operations `add_work`, `edit_work` and `finish_work`, STORE-042; served by the map module as the verb `work`, tool `map_work`, BASE-038; every read of an element or a join, a subtype join included, shows its `open_work`, STORE-025. The intake tools carry no condition field, BASE-039.
- Acceptance: An element with an open `tbd` record reads back with `open_work` `["tbd"]`, a join with an open `broken` record with `["broken"]`, and an object with none with `[]`; after `finish_work` the record reads back done with its resolution and the object's `open_work` is empty.
- Relates to: MAP-048, MAP-049, STORE-042, BASE-038, BASE-039, BASE-044, VIEW-005, VIEW-009, VIEW-020.
- Status: confirmed, 2026-09-27, for what `cruft` names and that Metaform has no legacy, and for the map as the whole intended project, the condition apart from the map, `tbd` in place of `missing`, the note and the task, held and reviewed, done with its resolution kept, critics writing the task with the finding, and any agent writing one at any time without a correction. Open: whether a work record lives in a layer, D84, and whether `tbd` is one condition whose task says build or decide, D85; both are built as recommended, a record of its own and one condition, until answered.

### MAP-047 An intake result is judged by what it says about the project

- Requirement: An intake result is judged by running the intake on a real project and grading the map on four things: it stays functionality based; it is accurate and thorough, missing no aspect of the functionality; it speaks to the project itself, never to the types of its elements; and its count of elements and joins does not blow up.
- What this means: Accuracy and thoroughness come first. Size is a cost that multiplies downstream, not a merit, so a smaller map is not better for being smaller; the count is watched only so that it does not blow up. A join that states a fact true of every artifact of its type, such as that an event bus delivers a published message to every current subscriber, speaks to an element type and fails. The grading applies to the map, never to the intake while it runs, MAP-013.
- Why: The map is what every later agent orients from. A map that speaks about types tells an agent nothing it did not already know, a map that misses a functionality sends agents into the code to find it, and a map that grows without bound costs every agent that reads it.
- How it shows: A grading of an intake names each of the four criteria with its finding.
- Build: No chassis mechanism: the store never judges content, MAP-013. The criteria are what a grading layer written by a module, a review, or an acceptance run of the Canonical Intake applies.
- Acceptance: None of its own.
- Relates to: MAP-013, MAP-020, MAP-040, LAYER-014.
- Status: confirmed, 2026-09-20; the size criterion as corrected, 2026-09-21.

---

### MAP-048 Tasks are written on the nodes the work concerns, and one command hands an agent everything the map holds there

- Requirement: The orchestrator keeps the task list and writes each task's instructions on the nodes the work concerns, and one command, on the command line or through the MCP server, hands an agent its task with everything the map holds for those nodes.
- What this means: Once Metaform is installed, an agent's work runs through the map. The orchestrator, the main agent, writes each task targeting the exact functions to be worked on, and the task shows on every node the work touches. The agent is told one command, which returns the task with everything the map holds for its nodes, the directions of the knowledge layers included. What comes with it asks the agent to review the knowledge layers first, tells it that other agents' memories are attached at those nodes, and asks it to record its own memories, LAYER-012. The rules that apply are listed, not carried in full, LAYER-021. While it works, the agent keeps a concise description of its progress on each node, written as a sentence that continues from the node's name, which the map shows in place of the node's label, VIEW-020. The map then serves as a kanban board: each node shows the work waiting on it, in progress and done.
- Why: The agent starts oriented: everything the map holds about the functions it will change reaches it in one read instead of being reconstructed, MAP-005, and each knowledge layer's directions reach it at the place they apply. Writing the task at the nodes, and the progress beside them, puts the state of the work where the work is, so a person reads it on the map and an agent reads it through the same reads.
- How it shows: A task written on two elements shows on both. The agent told the command receives the task with both elements' joins, work records, knowledge layer items and memories, and while it works each node's label is its sentence of progress.
- Build: Open, D92: what a task is and what holds it. The reads it draws on are `where`, STORE-025, and the node reads of LAYER-008.
- Acceptance: Open with D92.
- Relates to: MAP-046, MAP-049, MAP-051, LAYER-012, LAYER-017, LAYER-021, STORE-025, VIEW-020.
- Status: confirmed as design, 2026-09-26 and 2026-09-27. What a task is and where it is kept are open, D92.

### MAP-049 The task list is a work queue

- Requirement: The task list is a work queue served through the MCP server: agents see the outstanding tasks, and an agent that accepts one takes it off the list.
- What this means: A swarm of agents can each take one task by default, assigned by the orchestrator or taken from the list automatically. A task whose agent dies stays taken, showing its age on the node, until the orchestrator or the user puts it back on the list. A held work record, MAP-046, waits on the list until agents are assigned or take it, so tasks can be lined up and worked until the queue is clear, and a task can be reviewed for correctness before it is fired off. Tools carry permissions, so worker agents can be kept from creating layers, LAYER-018.
- Why: Many agents can work one project at once and never take the same task, and the list itself says what is waiting, so nothing has to watch the agents. A dead agent looks the same as a slow one from the list, so its task stays taken rather than being handed to a second agent that would duplicate the work; showing its age lets the orchestrator or the user decide.
- How it shows: Two agents each take one task from the list; neither sees the other's task as outstanding. A task taken by an agent that stopped shows its age on its node until it is put back.
- Build: Taking a task is built: `map work op=take id=<id>`, MAP-046, marks the record taken and refuses a second take. Listing what is outstanding is `map work open=true`. Putting a taken task back, showing a taken task's age, and assigning tasks are open, D92.
- Acceptance: A record taken once cannot be taken again. The rest is open with D92.
- Relates to: MAP-046, MAP-048, MAP-051, LAYER-018, MCP-003, VIEW-020.
- Status: confirmed as design, 2026-09-26 and 2026-09-27. Its records are open, D92.

### MAP-050 An agent asks its question at the node it concerns

- Requirement: An agent that needs an answer or a clarification adds a question at the node it concerns and carries on with what does not depend on the answer, and the user answers it in the web GUI.
- What this means: The question is attached where it applies, as a work record is. It stays open until the user answers it, and the answer is kept beside it. The web GUI shows every open question on the map, VIEW-021, and answering is one of its writes, VIEW-011. A critic's questions to the user show the same way.
- Why: The agent does not stop the work for an answer it does not need yet, and the question sits where a person looking at the map sees what it concerns; the answer stays at the node for the next agent that works there.
- How it shows: An agent asks at an element whether a function is still wanted and goes on with its other work; the element glows on the map until the user answers.
- Build: Open, D92: what holds a question and its answer.
- Acceptance: Open with D92.
- Relates to: MAP-046, VIEW-011, VIEW-021.
- Status: confirmed as design, 2026-09-26 and 2026-09-27. Its records are open, D92.

### MAP-051 A completed task is kept as past work at its node

- Requirement: A completed task leaves the task list and the node's label, and its record stays at the node as past work.
- What this means: An agent is not made to read past work; it is told past work is there. Each entry shows its age, recent or long ago, and carries the agent's work log. A work record done with its resolution, MAP-046, is kept the same way.
- Why: A finished task no longer steers anyone, so it leaves the list and the label. Kept at the node, it tells a later agent what was done there and when, if it wants to know, without spending the agent's context on history it does not need.
- How it shows: After an agent completes a task, the node's label no longer shows it, and the node's past work lists it with its age and the agent's log.
- Build: Open, D92.
- Acceptance: Open with D92.
- Relates to: MAP-046, MAP-048, MAP-049.
- Status: confirmed as design, 2026-09-26 and 2026-09-27. Its records are open, D92.

### MAP-052 The map is written out as a short Markdown document

- Requirement: `metaform map markdown` writes the functional map, or the part around one address, as a Markdown document that holds what a reader needs to find its way: each element's name, address, role and paths, and for each join its receiver, its provider, its relation, its purpose and its non_goal.
- What this means: With no address the document covers the whole map, the VE, the AUE and the DE first. With an address it covers that element, what it relies on and what relies on it, the view all around the place a reader is working. The function and the observation of a join are left out. The command is for the command line only and is not a tool.
- Why: A reader orients by what a part is for, who receives it and what stands around it; the relation says that in one sentence and the purpose says why. How a part works in detail is in its files, which the paths name, so repeating it in the document charges every reader for detail most do not need, and it goes out of date with the next change to the code where purpose stays true while the design holds. A document a person can read and pass on also lets the understanding of a system leave Metaform without the exchange document, which is for moving data and carries every id. It is not a tool because writing a document is an act of a person or an orchestrator, and every tool adds to what an agent meets when it connects, CLI-037.
- How it shows: `metaform map markdown address=code.chassis` prints the chassis with each join it receives and each it provides; `metaform map markdown file=map.md` writes the whole map to `map.md`.
- Build: The writer is `metaform.outline.markdown`, in the chassis, so the command and the web GUI's export, VIEW-024, give one document. A verb `markdown` of the map module, BASE-038, calls it, with `surfaces=('cli',)`, an optional noun `address` and an optional noun `file`. It reads through `roots` and `where` of STORE-025, so select, mask and hiding hold, STORE-028. An element is a heading of its short name, then its address, role and one `Paths:` line of its refs whose key is `path`. A join is a line naming receiver and provider by short name, then the relation as a sentence whose subject is the provider when `ef` is Function and the receiver when it is Encounter, then `Why:` with the purpose and `Not:` with the non_goal, each only when the join holds it. A subtype join is one line, its short name and its relation. With `file` the document is written there and the command says where; without, it is printed.
- Acceptance: The document of a map holds every element's name and address and every join's purpose, relation and non_goal, and holds no join's function or observation. The document of an address holds the joins that element provides as well as those it receives. The MCP tool list has no `map_markdown`.
- Relates to: BASE-038, STORE-025, STORE-028, MAP-020, MAP-047, CLI-037, VIEW-024.
- Status: confirmed, 2026-09-27: the fields and leaving out the function and the observation. The layout of the document is recommended.

## Open questions

1. Answered: the roots are code, document, media, data and stakeholder, as in the current Canonical Intake. Exterior is gone. (MAP-014)
2. Answered: a subtype never has a purpose of its own; a part with its own purpose is its own element. There are no receiver-end subtypes. (MAP-030)
3. Answered: a subtype's joins lift to the parent when it is annealed, D3; the element a subtype join holds that is still a join end is a node of the outer map until they do, MAP-032.
4. Answered: a part serving two joins is its own element, D4; an element held by two subtype joins is stored with a notice, MAP-032.
5. Answered, Rich 2026-09-27: a subtype join holds an ordinary element, so the question no longer arises, MAP-016 and MAP-030.
6. When there are several VEs, is one recorded as primary, and how?
7. Answered: the intake produces no properties; properties come from knowledge layers, MAP-022, MAP-040.
8. Answered: a subtype holds no subtypes, D5; a subtype join sits only inside a join held by a receiver, MAP-032.
9. Answered 2026-09-26: record by record through tool calls as it is reasoned, then a proofing pass over the whole recorded map before it finishes, MAP-040. The earlier answer was one submission after the whole method. Does the intake agent write its result as one whole submission or record by record through tool calls?
10. Answered: C(T) is the theory behind how a metaform works and describes no mechanism. No Type record stores a single encounter function. (MAP-001)
11. May a join have the same element as receiver and provider?
12. Are Type records shared across projects, as MAP-010 recommends, or kept in each project store, as STORE-008 has them?
13. Must an element created by a layer other than the intake carry a role? MAP-017 requires exactly one role on every element; STORE-009 allows none.
14. When a project holds more than one AUE, how is the set of elements belonging to each AUE recorded? (MAP-042)
15. Answered 2026-09-26: the intake text's response protocol says to record each object with the intake tools as it is reasoned; its schema defines the fields and is not returned as a document, MAP-040. NEW The Canonical Intake text asks for an XML answer, while the intake is to be written through Metaform's tools. See chassis section question 9. (MAP-040)
16. NEW The Canonical Intake's reading examples disagree on the root `code`: `code.loop.main` reads as main loop program code, and `code.bus.data.event` as event data bus code. Does a root carry a reading phrase, such as program code for `code`, or does every root read as its own name? (MAP-012)
17. Hard dependency is no longer a join role, MAP-022. Does it survive in any form, for example as a flag on a join marking that losing the provider breaks the receiver, or is it gone?
18. Answered, Rich 2026-09-27: an element record is its identity, address, name_length and role; the project's name for a functionality is on the join; its refs are rows linked to it, STORE-009. Before that, D78: identity and address only, with name, name_length, role and refs in a descriptor item. Earlier text: element records carry fields such as name, name_length, role, refs and extra (MAP-015, STORE-009), while element records are described as being just a namespace address, holding no data of their own, with things linked to them. Which fields, if any, does an element record keep, and where do the rest belong? (MAP-015, STORE-009, STORE-017)
19. NEW An element carries one role. When one project holds several AUEs and an element plays a different role for each, how is its role recorded? D87. (MAP-017, MAP-042)
20. NEW Which fields follow the voice of the relation, which element's name does each continue from, and where is an element's statement kept? D90. (MAP-020)
21. NEW Is a property a value attached to an element, a link between two elements, or a join of its own kind? D88. (MAP-022, STORE-039, LAYER-020)
22. NEW Does a work record live in a layer, D84, and is `tbd` one condition whose task says build or decide, D85? (MAP-046)
23. NEW What is a task, and what holds the queue, the progress sentences, questions and past work? D92. (MAP-048 to MAP-051)
24. NEW The Canonical Intake's wording where it differs from the decided shape: the element's name, the removal of absorbed subparts, the nested subtype join, the calls in its method, work records, and the voice. D99. (MAP-020, MAP-030, MAP-031, MAP-040, MAP-046)
