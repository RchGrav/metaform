# 01 The map: concept, mesh, namespace, elements, joins and subtypes

Scope: what a metaform is, the receiver, purpose and encounter structure it is made of, the namespace of types, element identity and roles, the join and its fields, subtypes produced by annealing, and how an intake result becomes these records.
Out of scope here: layers, provenance, memory and corrections, in section LAYER; tables and indexes, in section STORE; the module-facing data access object, in section BASE.

## Terms

These terms are used exactly as defined in the Canonical Intake.
- AUE, Artifact Under Examination: the thing being examined.
- VE, Vested Entity: the party vested in the type of thing the artifact is. It receives joins and holds Operative Purposes.
- VRE, Vested Receiving Entity: an element acting as the receiver of a join.
- PE, Providing Element: the element at the other end of a join, whose Encounter Function serves the receiver's Operative Purpose. PE is a position in a join, not a role.
- OP, Operative Purpose: the why, held by the receiver in its join.
- EF, Encounter Function: the how, the provider's function for that specific encounter, stored in the receiver's join.
- DE, Defining Element; SE, Supportive Element; NE, Notable Element: roles of elements inside the AUE. A Supportive Element's encounter is a function, MAP-022.
- AT, Artifact Type. Type: a namespace address and the reusable functional meaning it names.
- Element: a project's realization of a Type. Join: the receiver-owned record of one encounter.
- Subtype: an element that annealing absorbed into a join it shares with its parent functionality. It keeps its own encounter function and has no purpose of its own.

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
- What this means: Each join is one receiver's why served by one provider's how. When two elements need each other, they hold two different purposes, so they are two joins: one owned by the first element and served by the second, and one owned by the second and served by the first. Neither join is the other reversed. A join is stored with its receiver and is directly addressable within that ownership.
- Why: A single meaning per join keeps every join readable on its own and keeps the receiver, purpose and encounter structure acyclic. The Encounter Function is stored in the receiver's join because one provider may serve different receivers through different encounters.
- How it shows: Reading an element's joins as receiver returns the joins it owns. Reading them as provider returns joins owned by other elements. The two lists never mix.
- Build: A join record has a stable join id, the receiver element id as owner, the provider element id, and the fields in MAP-020. A join is read by its id, by receiver, or by provider. There is no reverse or bidirectional join record.
- Acceptance:
  1. Reading element A as receiver lists only joins A owns; reading A as provider lists only joins where A is the provider.
- Relates to: MAP-002, MAP-020, STORE-010.
- Status: confirmed.

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
- What this means: `code.bus.data.event` reads as event data bus code. `data.bill_of_materials` reads as bill of materials data. name_length is the lookback segment count: with name_length 2, `code.engine.game` has the short name game engine. The readable name is presentation. It never replaces the stored address as identity.
- Why: Reading addresses as proper nouns engages the model's existing understanding of types directly, without reasoning. Short names keep references readable.
- How it shows: Every element and Type listing shows the address and its reading.
- Build: reading(address) reverses the segments, replaces underscores with spaces, and joins with spaces. Every root reads as its own name. short_name(address, n) reverses the last n segments, replaces underscores with spaces and joins them. When n is null, zero, or larger than the number of segments, short_name returns reading(address). Readings are computed, never stored as identity.
- Acceptance:
  1. reading of `code.bus.data.event` is event data bus code; short_name of `code.engine.game` with name_length 2 is game engine; short_name with name_length 9 is game engine code.
- Relates to: MAP-010, MAP-015.
- Status: confirmed for the reading rule. The Canonical Intake has two reading examples that disagree on the root: `code.loop.main` reads as main loop program code, and `code.bus.data.event` as event data bus code. The build reads every root as its own name until open question 16 is answered. The edge cases of short_name are recommended.

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

### MAP-015 An element is a project's realization of a Type, with a stable id

- Requirement: An element has a stable id in its project that survives any change of its Type.
- What this means: The address says what kind of thing an element is. The element is this artifact's realization of it. A later intake or a correction can type the same element better, and everything attached to that element, its joins, subtypes, layer items and memory, follows it through the change instead of being orphaned. Names are lexical handles only; identity is never established by string equality of names.
- Why: Retyping is how the map improves. If identity were the address, every improvement would orphan the knowledge built on the element. Relocating an element through a correction layer takes everything attached to it along; its joins do not survive the move, because a join is the face between a specific receiver and provider, LAYER-011 and STORE-017.
- How it shows: After an element's address changes, its joins, subtypes and layer items are all still found at the element under its new address.
- Build: An element record has element id, project id and address, and nothing else. Its name, name_length, role and refs, where given, are a descriptor item linked to it, STORE-009. Joins, subtypes and layer items reference element ids, never addresses. Writes that name an element by address resolve it to its id within the project at write time. Changing an element's address is a correction, made by a correction layer, LAYER-011; it keeps the element id and everything attached to the element follows it. An element is only a namespace address: when a correction layer removes an element, what was attached to it is orphaned, kept and not shown, and when an element is put back at the same address, that same element identity is restored and what was attached shows again, STORE-017.
- Acceptance:
  1. Relocating an element from `code.probe` to `code.probe.echo` keeps its id, and its layer items and memories are returned when reading it at the new address; its joins as receiver and as provider are no longer current, and joins at the new place are new joins.
- Relates to: MAP-016, MAP-020, LAYER-011, STORE-007, STORE-009.
- Status: confirmed.

### MAP-016 One element per address per project in a map

- Requirement: Within one project's functional map, an address identifies at most one element.
- What this means: The intake traces an element that bears an Operative Purpose as a receiver without creating a duplicate record. The same element may be a receiver in some joins and a provider in others. Any reference to an element, in a join or anywhere else, uses its address, and an address with no element is not a valid reference.
- Why: One record per realized Type keeps every join about that element in one place, so an agent reads the element's receivers, purposes and encounters in one read.
- How it shows: Writing an element at an address that already has one returns the existing element.
- Build: The pair project and address is unique among current root elements of a project. A write that names an unknown address as a join's receiver or provider fails with one next step: add the element first.
- Acceptance:
  1. A second write of an element at an existing address in the same project returns the first element's id and creates no new element.
- Relates to: MAP-015, MAP-031.
- Status: recommended. Whether a subtype and a root element may share an address is open, see open question 5.

### MAP-017 Every element carries exactly one role

- Requirement: An element carries exactly one role: AUE, VE, DE, SE or NE.
- What this means: AUE marks the artifact under examination. VE marks a party outside the artifact whose purpose drives changes or improvements to it; it is never the person who asked for the intake, the end user, or whoever performs the operation, and it is named at its most specific reusable type level. DE is the element whose loss would stop the artifact being the same type; its function is stated independently of medium, encoding, genre and style. SE is an element whose Encounter Function helps the DE serve the VE's purpose. NE is a component, interface or specification that states an essential demand on its environment. Inside the AUE, an element is DE, SE or NE. A VE is an element with role VE and never receives an AUE role. PE is not a role; it is a join's other endpoint. A subtype carries DE, SE or NE.
- Why: Roles tell an agent at once how an element bears on the artifact's identity, which is the first thing it needs to orient.
- How it shows: Every element listing shows its role.
- Build: The intake writes exactly one role, from the set above, on every element and subtype it creates: an element's role is in its descriptor item, STORE-009, and a subtype's in its own record, STORE-011. There may be several VEs. The store records the role as given and does not refuse a missing one, STORE-009 and STORE-026, because the store never judges content; a missing role on an intake element is a defect of that intake, visible to any later layer that grades the map.
- Acceptance: None beyond the intake mapping test in MAP-031.
- Relates to: MAP-020, MAP-030, MAP-031.
- Status: confirmed. Whether one VE is recorded as primary is open, see open question 6. STORE-009 allows an element with no role; whether an element created by a layer other than the intake must carry one is open, see open question 13.

---

### MAP-020 A join records one encounter in full

- Requirement: A join records its type, receiver, provider, purpose, function, ef, relation, verb, observation, optional non_goal and optional refs.
- What this means:
  - type: the kind of join. Intake writes type purpose. Modules may define other join types, and unknown valid content survives reads, edits, copies and export.
  - receiver: the element that owns the join and holds the purpose.
  - provider: the element whose function serves the purpose.
  - purpose: the active Operative Purpose statement, the why.
  - function: the provider's Encounter Function for this specific encounter, the how.
  - ef: the Encounter Function's word, one of two: Function if it is the encounter of a functionality, or Encounter if it is the functionality of the encounter. A subtype join carries its own, MAP-030.
  - relation: an active-voice descriptive fragment that starts directly with a third-person singular present-tense verb ending in -s or -es. Its subject follows ef: the provider when ef is Function; when ef is Encounter, the Vested Entity on a top-level join and the Receiving Entity in a subtype join, since the Vested Entity is only ever at the top, Rich 2026-09-27.
  - verb: the verb of the relation, a third-person singular present-tense active verb ending in -s or -es, as the intake agent infers it. It is the agent's word, never a set list. A subtype join carries its own, MAP-030.
  - observation: the actual real-world condition, format, layout or limitations of what is there.
  - non_goal: an outcome the receiver does not seek, recorded only where it materially clarifies the purpose.
  - refs: type-specific or artifact-specific references or logic, only where needed.

  An encounter function states a function. A language, medium or encoding never goes into an encounter. A join speaks about this artifact. Its purpose and function state what this artifact actually does in its own particulars. Where the artifact represents something, the join describes the function of that representation within the artifact, not the real-world function of the thing represented.
- Why: Functions live in joins, and joins speak to the artifact. Keeping each field separate lets an agent ask one question at a time, who, why, how, what is actually there, and get a direct answer.
- How it shows: Reading a join returns every field it was written with, each on its own.
- Build: Each field is its own column. Nothing is packed into a shared text or JSON field except extension content of module-defined join types, which is stored and returned intact. `type` is `purpose` for every join the intake writes; a module-defined type is any other name in the address form of MAP-010, declared by the module that writes it. purpose, function, relation and observation must be present, not null, on purpose joins; an empty string is stored as given, STORE-026. `ef` holds only `Function` or `Encounter`; any other value is kept in the join's `extra` and named in a notice, and a missing one is named, BASE-044. `verb` is stored as given, and a missing one is named. non_goal is nullable. refs follow MAP-021.
- Acceptance:
  1. A join written with every field, including a non_goal and two refs, reads back with each field equal to what was written.
  2. A join of a module-defined type with extension content survives export and import unchanged.
  3. A join or subtype written with an `ef` of `Both` reads back with no `ef`, the word kept in its `extra` and a notice naming `ef`; a correction that changes another field keeps the `ef`.
- Relates to: MAP-003, MAP-021, MAP-022, STORE-010, STORE-021.
- Status: confirmed. `verb` and the relation's subject: Rich, 2026-09-26: the intake agent infers the relation's verb into its own field; this changes the relation's grammar rules but not the intake's semantics, adding one prompt and one field. `ef`: Rich, 2026-09-26, on the Encounter Function: the model writes "Function if it is the encounter of a functionality, or Encounter if it is the functionality of the encounter", and the word is a binary choice between the two, not freeform inference.

### MAP-021 Refs are an ordered key and value list

- Requirement: Elements, joins and subtypes carry refs as an ordered list of key and value pairs.
- What this means: refs hold references such as key path with a relative file path, or other type-specific keys. The same key may appear more than once, for example several member paths. A file name or path is legal in a ref and never legal as a namespace address.
- Why: One uniform shape serves any artifact type without a schema per type, and repeated keys let a join list every member of a grouped Artifact Type.
- How it shows: A join grouping three files lists three path refs in the order written.
- Build: Each ref is its own record with owner, position, key and value, indexed by owner and by key and value, so an agent can find every element or join citing a given path directly.
- Acceptance:
  1. Looking up key path with a given file returns every join and subtype whose refs cite it, including subtypes inside joins.
- Relates to: MAP-020, MAP-030, STORE-012, STORE-025.
- Status: confirmed.

### MAP-022 Every encounter is a function or a property

- Requirement: Every encounter is either a function, carried by a join, or a property, carried by a transitive property record attached to an element; properties never have joins.
- What this means: Both are encounters. A function encounter is a join: a receiver's purpose served by a provider's function, MAP-020. A join is always a function encounter; there is no property join and no join kind. Supportive is a kind of encounter function: a Supportive Element's encounter is a function, carried by a join. A property is its own record: the element it is attached to, its value, and the layer that owns it, STORE-039. A property attaches only to an element, never to a bare namespace address, a join or a subtype. When a property belongs at a namespace prefix where the project has no element, such as a practice for `code` in general, the knowledge layer creates an element at that prefix, as a layer may create a new element, and attaches the property to it. The namespace tree itself links that element to every element above it, so no join is needed, and its properties apply up to the leaves from there. It is transitive along the namespace from that element's address, LAYER-005: from the address where it is linked, inference goes down to the trunk, and going up it follows to the leaves. Orientation: the trunk is down and the leaves are up. So Bash attached as a property to the installer element applies up toward the leaves at every address above the installer and is visible down at `code`, and a property linked near the trunk applies to every branch after it. Knowledge layers work the same way, LAYER-016: a knowledge item is either a property, transitive and attached to an element, including an element the knowledge layer created and linked to the metaform, or a function, a join. Hard dependency, property and supportive are no longer join roles.
- Why: A function stays with the one receiver it serves, so it belongs in that receiver's join. A property describes what something is, so it flows along the namespace to everything above it and shows at the trunk; giving it a join would tie it to one receiver and stop it flowing. Two kinds of encounter, one carried by joins and one by properties, keep one model for the map and every knowledge layer.
- How it shows: A property linked at an address appears as applying at every address above it toward the leaves and as visible at the trunk; a join appears only as its receiver's join.
- Build: Joins are stored as in STORE-010, with no kind column. Properties are stored as in STORE-039 and read through STORE-035: the applying set at an address holds the properties attached to the elements at it and at every prefix; the visible set holds the properties attached to elements above it toward the leaves. The intake produces no properties; properties come from knowledge layers, MAP-040. Until the intake text emits them, the intake tools record only elements, joins and subtype joins, and properties come from knowledge layers.
- Acceptance:
  - With Bash attached as a property to the element at `code.installer`: a read at `code.installer.script` receives Bash as applying; a read at `code` shows Bash as visible and not applying; a read at `code.engine` does not receive it.
  - A join from `code.installer` to a provider is received only as that receiver's join and at no other address.
  - No write path accepts a join marked as a property.
- Relates to: MAP-020, MAP-011, LAYER-005, LAYER-016, STORE-010, STORE-035, STORE-039.
- Status: creating an element at a prefix to hold a property there, linked by the namespace tree with no join, is recommended. Confirmed that every encounter is a function or a property, that properties are transitive records attached only to elements with no joins, that supportive is a function, and the orientation above. The intake produces no properties; they come from knowledge layers. Whether hard dependency survives in any form is open, open question 17.

### MAP-030 Annealing produces subtypes inside the one join they share

- Requirement: An element absorbed by annealing is kept as a subtype inside the one join it shares with its parent functionality, carrying its own encounter function and never a purpose of its own.
- What this means: Annealing combines parts that share a join into a bigger functionality that describes them all. Each part serves the same receiver's purpose through the same join. The bigger functionality becomes the provider of a combined encounter, and each part hangs under that combined encounter, keeping its own encounter function. Two probes absorbed by a failsafe, serving a daemon's purpose of catching a dead gateway, are subtypes of the failsafe's join.

  A subtype has no purpose of its own. A part that holds its own purpose is not sharing the same join: it is its own receiver with its own join, so it is promoted to its own element and is not a subtype. A command line and a status page that each need node state from a control API each hold their own purpose, so each is an element with its own join to the control API.

  Absorbing is legal only when the parts share that join and the combined encounter covers each part's encounter function. Combining never optimizes a functionality away.
- Why: Annealing keeps the root map minimal, coarse and shallow without discarding any functionality. A subtype exists only because it shares that join, so the join is where it lives. A purpose is what gives a part its own join, so a part with a purpose cannot live inside another's join.
- How it shows: Reading a join returns its purpose and combined function, and beneath them each subtype with its own function.
- Build: A subtype record has subtype id, join id, address, name, name_length, role, its own function, its own ef, relation, its own verb, observation and refs. It has no purpose field and no end field. The join record holds the purpose and the combined function. Coverage is the intake agent's judgment and is never checked by the store.
- Acceptance:
  1. A join with two subtypes reads back with the purpose and combined function on the join and each subtype's own function, relation and observation under it.
  2. A submission that gives a subtype a purpose is stored as given: the purpose is kept in the subtype's `extra`, and the result carries a notice naming the subtype, BASE-044.
- Relates to: MAP-031, MAP-032, MAP-040, STORE-011.
- Status: confirmed.

### MAP-031 A subtype is reachable only through its join and is never a root

- Requirement: A subtype is never a root element and never a join's receiver or provider, and it is reached only through the join that holds it.
- What this means: The absorbed element is not mapped to the external graph. It still keeps its own address, relation and encounter function, and layers and memory attach to it directly by its subtype id.
- Why: Keeping subtypes inside the join is what keeps the root map minimal. Keeping them addressable is what lets memory and layers still reach the specific part.
- How it shows: Listing a project's elements does not show subtypes. Reading a subtype's address returns it with the join that holds it.
- Build: Subtypes are stored separately from elements. A join's receiver and provider reference element ids only, so a subtype cannot become a join endpoint by construction. Reading by a subtype's address returns the subtype and its holding join.
- Acceptance:
  1. After storing a map with subtypes, the element listing contains no subtype, and reading a subtype's address returns it with its holding join's id, receiver and provider.
  2. A layer item attached to a subtype is returned when reading that subtype.
- Relates to: MAP-030, LAYER-003, STORE-011.
- Status: confirmed.

### MAP-032 Subtype nesting and ownership limits

- Requirement: The limits on what a subtype may own and hold are settled before storage fixes them.
- What this means: Three cases are not yet settled: whether a subtype may be the receiver of joins of its own after annealing; whether one element may be a subtype in two different joins; whether a subtype may itself hold subtypes.
- Why: Each answer changes what the store must allow or forbid, and guessing would bake a wrong rule into the schema.
- How it shows: Not yet specified.
- Build: Until the open questions are answered the store allows none of the three: a join's receiver and provider must be elements, never subtypes, STORE-010; a subtype address is held by at most one current subtype, and never by a current element, STORE-011; a subtype has no subtypes, because `add_subtype` takes a join, never a subtype.
- Acceptance: None yet.
- Relates to: MAP-030, MAP-031.
- Status: open, see open questions 3, 4 and 8.

---

### MAP-040 An intake result becomes map records

- Requirement: An intake is recorded through the intake module's tools one object per call, as it is reasoned, and stored as elements, joins, subtypes and refs in one intake layer, with nothing lost.
- What this means: The intake's instructions are delivered to the performing agent by name. The agent records the map as it works the method: it starts the intake, records each element, join and subtype join in its own call as soon as it is reasoned, and, once everything is recorded, performs the proofing pass of step 12: it reads the recorded map back whole, checks it against the artifact and the intake document, corrects it, anneals it and completes it, then finishes the intake, BASE-039. The tools never parse the intake's XML: each takes one object's fields, named as in the intake's response schema, which is the metaform's general data pattern: elements, joins held by receivers with purpose and function, subtype joins inside their parent join with their own function and no purpose, and refs. The intake text can change as long as its data still follows that pattern, with no change to the tools. The intake produces no properties; properties come from knowledge layers, MAP-022.
- Why: The map is only useful if everything the intake agent recorded can be read back exactly, and the intake agent's inference is the expensive part. A schema owned by the tools keeps storage stable while the intake text improves. Rich, 2026-09-26: an intake is long, so the agent records the map as it builds it and the web GUI shows each object as it arrives; once everything is recorded, the agent proofs it. Recording as it goes improves the result and lets agents with smaller context windows perform the same intake, since no agent has to hold the whole map in its head: the system helps the agent build the metaform.
- How it shows: While the intake is recorded, the web GUI draws each object as it arrives, VIEW-005, and no context read sees the intake. After the intake finishes, every element, join, subtype and ref recorded is readable from the store.
- Build: `intake_start` opens one building intake layer with its provenance record, LAYER-010; each `intake_element`, `intake_join` and `intake_subtype` call writes one object into it, STORE-024; `intake_show` reads it back whole through the store read `layer_graph`, STORE-025; `intake_edit` and `intake_remove` change it in place while it is building, STORE-032; `intake_finish` marks it ready, and from then on it changes only through correction layers, STORE-017. The current intake schema, `specifications/Canonical_Intake.xml`, maps to the tools and the store as follows:

  | Intake XML | Tool field | Store |
  |---|---|---|
  | `result@id` | `intake_start` `id` | `layers.result_id` of the intake layer |
  | `element@namespace_address` | `intake_element` `address` | `elements.address` with a new identity id, STORE-009; the address row in `types`, STORE-008 |
  | `element/name` text | `intake_element` `name` | descriptor item of the intake layer on the element, STORE-009 |
  | `element@name_length` | `intake_element` `name_length` | descriptor item |
  | `element@role` AUE, VE, DE, SE, NE | `intake_element` `role` | descriptor item |
  | none in the current schema for a root element | `intake_element` `refs` | `refs` rows owned by the descriptor item |
  | `join`, held inside its receiving element's `joins` | `intake_join`, `receiver` the enclosing element's address | `joins` row, STORE-010 |
  | `join@type`, always `purpose` | `intake_join` `type`, `purpose` when left out | `joins.type` |
  | `join@provider` | `intake_join` `provider` | `joins.provider`, the provider's identity id resolved by address |
  | `join@purpose`, `@function`, `@ef`, `@relation`, `@verb`, `@observation`, `@non_goal` | `intake_join`, same names | same-named `joins` columns, MAP-020 |
  | `join/refs/ref@key`, `@value` | `intake_join` `refs` | `refs` rows owned by the join, in order, STORE-012 |
  | nested `join` inside a `join` | `intake_subtype`, `join` the parent join's id | `subtypes` row in that join, STORE-011 |
  | nested `join@function`, `@ef`, `@relation`, `@verb`, `@observation` | `intake_subtype`, same names | same-named `subtypes` columns |
  | nested `join@provider`, the nested `element@namespace_address` | `intake_subtype` `address` | `subtypes.address` |
  | nested `element/name`, `@name_length`, `@role` DE, SE, NE | `intake_subtype` `name`, `name_length`, `role` | same-named `subtypes` columns |
  | nested `element/refs/ref` | `intake_subtype` `refs` | `refs` rows owned by the subtype |

  Built this way the structure follows the pattern that makes it acyclic: each join is held by its receiver and runs one way to its provider, a subtype sits inside its one join with no purpose, and a relationship in the other direction is its own join with its own purpose, MAP-020 and MAP-030. Only the element-to-element view, which ignores purposes, can show a cycle. A join whose provider is its own receiver is stored as given with a notice, D82.

  When the result has no element with role AUE, none is created. The artifact is still recorded by the project's target, MAP-041.
- Acceptance:
  1. Recording a real intake result, such as the MGM map, then reading the project back yields the same set of root elements with their names, name lengths and roles, joins with every field, subtypes with their functions, and refs in order.
  2. No subtype in the result appears as a root element after storing.
- Relates to: MAP-015, MAP-020, MAP-021, MAP-030, LAYER-001, LAYER-010, STORE-009, STORE-013, STORE-024, BASE-039, MCP-009.
- Status: confirmed 2026-09-26: recorded one object per call as it is reasoned, read back and proofed in step 12, then finished; the tools' own fields; the mapping of root elements, joins, nested subtype joins and refs. The handling of a missing AUE is recommended.

---

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
- Status: confirmed for the distinction; open for recording which elements belong to each AUE when a project holds several.

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

### MAP-046 Intake findings flag objects as missing, broken or cruft
- Requirement: Each element and join the intake records can carry a finding flag, missing, broken or cruft, with a short note; working is the default.
- What this means: Working code goes in the main metaform as normal, unflagged. `missing` is a function that is part of the project's current specs but is not built; it shows when the agent reviews the whole repository, specs included. `broken` is something in the intake target that is broken, not working, not connected or orphaned. `cruft` is left-over code that is disabled and needs cleaning up. A flagged object is still part of the map, in its place, with its joins, and every read shows its flag, so an agent reading the map sees the finding where it applies.
- Why: The intake agent sees the whole project, specs included, and what it finds wrong or unfinished is as valuable as the working map. Kept on the object it concerns, a finding reaches the next agent exactly where it is working, and the flags can be listed to plan fixes and clean-up.
- How it shows: An intake of a repository with a disabled legacy module flags that module's element `cruft` with the note `disabled since the 2.0 rewrite`. `metaform map findings flag=cruft` lists it.
- Build: `flag` and `flag_note` as fields of `intake_element`, `intake_join` and `intake_subtype`, and changed with `intake_edit` while the intake is building, BASE-039; stored per STORE-042; shown by every read, STORE-025.
- Acceptance: An intake with one element of each flag reads back each flag on its element, and a working element has no flag.
- Relates to: BASE-039, STORE-042, MAP-040, BASE-045.
- Status: confirmed. Keeping flagged objects in the map in their places is recommended.

## Open questions

1. Answered: the roots are code, document, media, data and stakeholder, as in the current Canonical Intake. Exterior is gone. (MAP-014)
2. Answered: a subtype never has a purpose of its own; a part with its own purpose is its own element. There are no receiver-end subtypes. (MAP-030)
3. Can a subtype be the receiver of joins of its own after annealing, or do its joins lift to the parent?
4. Can one element be a subtype in two different joins, such as one probe serving two failsafes?
5. May a subtype share an address with a root element of the same project?
6. When there are several VEs, is one recorded as primary, and how?
7. Answered: the intake produces no properties; properties come from knowledge layers, MAP-022, MAP-040.
8. May a subtype hold subtypes of its own?
9. Answered 2026-09-26: record by record through tool calls as it is reasoned, then a proofing pass over the whole recorded map before it finishes, MAP-040. The earlier answer was one submission after the whole method. Does the intake agent write its result as one whole submission or record by record through tool calls?
10. Answered: C(T) is the theory behind how a metaform works and describes no mechanism. No Type record stores a single encounter function. (MAP-001)
11. May a join have the same element as receiver and provider?
12. Are Type records shared across projects, as MAP-010 recommends, or kept in each project store, as STORE-008 has them?
13. Must an element created by a layer other than the intake carry a role? MAP-017 requires exactly one role on every element; STORE-009 allows none.
14. When a project holds more than one AUE, how is the set of elements belonging to each AUE recorded? (MAP-042)
15. Answered 2026-09-26: the intake text's response protocol says to record each object with the intake tools as it is reasoned; its schema defines the fields and is not returned as a document, MAP-040. NEW The Canonical Intake text asks for an XML answer, while the intake is to be written through Metaform's tools. See chassis section question 9. (MAP-040)
16. NEW The Canonical Intake's reading examples disagree on the root `code`: `code.loop.main` reads as main loop program code, and `code.bus.data.event` as event data bus code. Does a root carry a reading phrase, such as program code for `code`, or does every root read as its own name? (MAP-012)
17. Hard dependency is no longer a join role, MAP-022. Does it survive in any form, for example as a flag on a join marking that losing the provider breaks the receiver, or is it gone?
18. Answered: an element record holds only identity and address; name, name_length, role and refs are a descriptor item linked to it, STORE-009, D78. Earlier text: element records carry fields such as name, name_length, role, refs and extra (MAP-015, STORE-009), while element records are described as being just a namespace address, holding no data of their own, with things linked to them. Which fields, if any, does an element record keep, and where do the rest belong? (MAP-015, STORE-009, STORE-017)
