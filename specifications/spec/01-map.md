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
- DE, Defining Element; SE, Supportive Element; NE, Notable Element: roles of elements inside the AUE.
- AT, Artifact Type. Type: a namespace address and the reusable functional meaning it names.
- Element: a project's realization of a Type. Join: the receiver-owned record of one encounter.
- Subtype: an element that annealing absorbed into a join it shares with its parent functionality.

---

### MAP-001 A metaform records identity as C(T)

- Requirement: A metaform records each Type's identity as the set C(T) = { (r_i AND p_i AND e) }, where each Receiving Entity r_i is bound to its Operative Purpose p_i and the Type's Encounter Function e.
- What this means: A thing is what it is because of who receives it, why they hold it, and how it serves them. The conjunction is exact: a receiver without its purpose, or a purpose without the encounter that serves it, is not part of the identity. C(T) is a semantic definition. It is not a similarity score, a confidence, a lower bound or a gate. A realization can change substantially and keep its identity as long as C(T) holds. Mutation changes the realization and keeps C(T). Transformation changes C(T), which means the thing has become something else.
- Why: Placing identity in semantic relations, instead of in a frozen part of the content, lets the realization change freely while the identity stays stable. It also turns an inference-heavy question, what is this and what must it keep doing, into a structure an agent reads instead of reconstructs. Cost in Metaform means orientation inference an agent no longer has to spend, and C(T) is where that saving comes from.
- How it shows: Reading every join whose provider realizes a Type returns that Type's receivers, their purposes and the encounters that serve them, in one read.
- Build: The identity of the Type realized by element X in a project is read as all current joins in that project whose provider is X, each returned as receiver, purpose and function. No stored field holds C(T); it is always this read. The store never evaluates C(T) to accept or refuse a write.
- Acceptance:
  1. Given three joins with provider X from three receivers, the C(T) read for X returns exactly those three triples with their purposes and functions, and nothing from joins where X is the receiver.
  2. No write of an element or join is refused on the grounds that it changes C(T).
- Relates to: MAP-002, MAP-010, MAP-011, STORE-010, STORE-025, LAYER-011.
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
- Build: Nothing beyond the records it explains: MAP-001, MAP-002, MAP-011, MAP-012 and LAYER-001. No component computes basins or embeddings; the basin is the C(T) read of MAP-001.
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
- How it shows: Content attached at `code.engine` applies when reading `code.engine.game.fps`. Content attached at `code.engine.game.fps` does not appear when reading `code.engine`.
- Build: Reading a Type's inherited context walks its prefixes from the trunk up to the Type itself, in that order. The walk never visits children. Attaching and selecting content along this walk is specified in LAYER.
- Acceptance:
  1. An item attached at `code` is returned when reading inherited context at `code.engine.game`; an item attached at `code.engine.game` is not returned when reading inherited context at `code`.
- Relates to: MAP-010, LAYER-005, LAYER-007.
- Status: confirmed. Attaching content at a type address that no element holds is open, per LAYER open question 10.

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
- Build: The root list is data, not code, so a change to it needs no code change. Each entry holds the root name and its reading phrase, MAP-012: code with program code, and document, media, data and stakeholder each reading as its name, until D1 is answered. The store does not refuse an address under another root, per MAP-013.
- Acceptance: None; the list is data and low impact.
- Relates to: MAP-010, MAP-013.
- Status: open. REQUIREMENTS.md names asset in place of media and an entity trunk, and the repository's development instructions name exterior as a base. See open question 1.

### MAP-015 An element is a project's realization of a Type, with a stable id

- Requirement: An element has a stable id in its project that survives any change of its Type.
- What this means: The address says what kind of thing an element is. The element is this artifact's realization of it. A later intake or a correction can type the same element better, and everything attached to that element, its joins, subtypes, layer items and memory, follows it through the change instead of being orphaned. Names are lexical handles only; identity is never established by string equality of names.
- Why: Retyping is how the map improves. If identity were the address, every improvement would orphan the knowledge built on the element.
- How it shows: After an element's address changes, its joins, subtypes and layer items are all still found at the element under its new address.
- Build: An element record has element id, project id, address, name, name_length, role, and refs as in MAP-021. Joins, subtypes and layer items reference element ids, never addresses. Writes that name an element by address resolve it to its id within the project at write time. Changing an element's address is a correction to the map layer, specified in LAYER, and never creates a new element id.
- Acceptance:
  1. Retyping an element from `code.probe` to `code.probe.echo` keeps its id, and its joins as receiver and as provider, its subtypes and its layer items are all returned when reading it at the new address.
- Relates to: MAP-016, MAP-020, LAYER-011, STORE-007, STORE-009.
- Status: confirmed.

### MAP-016 One element per address per project in a map

- Requirement: Within one project's functional map, an address identifies at most one element.
- What this means: The intake traces an element that bears an Operative Purpose as a receiver without creating a duplicate record. The same element may be a receiver in some joins and a provider in others. Any reference to an element, in a join or anywhere else, uses its address, and an address with no element is not a valid reference.
- Why: One record per realized Type keeps every join about that element in one place, which is what makes C(T) a single read.
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
- Build: The intake writes exactly one role, from the set above, on every element and subtype it creates. There may be several VEs. The store records the role as given and does not refuse a missing one, STORE-009 and STORE-026, because the store never judges content; a missing role on an intake element is a defect of that intake, visible to any later layer that grades the map.
- Acceptance: None beyond the intake mapping test in MAP-031.
- Relates to: MAP-020, MAP-030, MAP-031.
- Status: confirmed. Whether one VE is recorded as primary is open, see open question 6. STORE-009 allows an element with no role; whether an element created by a layer other than the intake must carry one is open, see open question 13.

---

### MAP-020 A join records one encounter in full

- Requirement: A join records its type, receiver, provider, purpose, function, relation, observation, optional non_goal and optional refs.
- What this means:
  - type: the kind of join. Intake writes type purpose. Modules may define other join types, and unknown valid content survives reads, edits, copies and export.
  - receiver: the element that owns the join and holds the purpose.
  - provider: the element whose function serves the purpose.
  - purpose: the active Operative Purpose statement, the why.
  - function: the provider's Encounter Function for this specific encounter, the how.
  - relation: the relation stated in active voice.
  - observation: the actual real-world condition, format, layout or limitations of what is there.
  - non_goal: an outcome the receiver does not seek, recorded only where it materially clarifies the purpose.
  - refs: type-specific or artifact-specific references or logic, only where needed.

  An encounter function states a function. A language, medium or encoding never goes into an encounter. A join speaks about this artifact. Its purpose and function state what this artifact actually does in its own particulars. Where the artifact represents something, the join describes the function of that representation within the artifact, not the real-world function of the thing represented.
- Why: Functions live in joins, and joins speak to the artifact. Keeping each field separate lets an agent ask one question at a time, who, why, how, what is actually there, and get a direct answer.
- How it shows: Reading a join returns every field it was written with, each on its own.
- Build: Each field is its own column. Nothing is packed into a shared text or JSON field except extension content of module-defined join types, which is stored and returned intact. `type` is `purpose` for every join the intake writes; a module-defined type is any other name in the address form of MAP-010, declared by the module that writes it. purpose, function, relation and observation must be present, not null, on purpose joins; an empty string is stored as given, STORE-026. non_goal is nullable. refs follow MAP-021.
- Acceptance:
  1. A join written with every field, including a non_goal and two refs, reads back with each field equal to what was written.
  2. A join of a module-defined type with extension content survives export and import unchanged.
- Relates to: MAP-003, MAP-021, MAP-022, STORE-010, STORE-021.
- Status: confirmed.

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

### MAP-022 Roles within a join

- Requirement: A join may state the role the provider plays for the receiver.
- What this means: The Metaform foundation names three roles in a join: hard dependency, property and supportive. Property joins carry transitivity in the map itself. A property typically follows the transitive rule of where it is linked: from the address where the property is linked, inference goes down to the trunk, and going up it follows to the leaves. Orientation: the trunk is down and the leaves are up. So Bash linked as a property of the installer applies up toward the leaves at every address above the installer and is visible down at `code`, and a property linked near the trunk applies to every branch after it. The Canonical Intake currently writes only join type purpose and does not record a role in the join.
- Why: The role in a join tells an agent whether losing the provider breaks the receiver, changes one of its properties, or only weakens its support.
- How it shows: Not yet observable.
- Build: A property join's transitivity follows LAYER-005 along the namespace from the address where the property is linked: it applies up toward the leaves and is visible down toward the trunk. How a join records its role is not specified until the open question is answered.
- Acceptance: With Bash linked as a property join at `code.installer`: a read at `code.installer.script` receives Bash as applying; a read at `code` shows Bash as visible and not applying; a read at `code.engine` does not receive it.
- Relates to: MAP-020, MAP-011, LAYER-005, STORE-010.
- Status: confirmed that property joins carry transitivity in the map itself, with the orientation above. Whether and how the roles hard dependency, property and supportive are recorded on joins is open, see open question 7.

---

### MAP-030 Annealing produces subtypes inside the one join they share

- Requirement: An element absorbed by annealing is kept as a subtype inside the one join it shares with its parent functionality, at the receiver end or the provider end.
- What this means: Annealing combines elements that share a join into a bigger functionality that describes them all. The subtypes do not share the whole join; they share all of it except the end where they differ.
  - Provider end: several parts each serve the same receiver's purpose. The bigger functionality becomes the provider of a combined encounter, and each part hangs under that combined encounter, keeping its own encounter function. Two probes absorbed by a failsafe, serving a daemon's purpose of catching a dead gateway, are provider-end subtypes.
  - Receiver end: several parts each hold the same purpose served by the same provider. The bigger functionality becomes the receiver of a combined purpose, and each part hangs under that combined purpose, keeping its own purpose. A command line and a status page absorbed by an operator interface, both needing node state from a control API, are receiver-end subtypes.

  Absorbing is legal only when the subparts share that join and the combined node covers them: at the provider end the combined encounter covers each subtype's encounter, and at the receiver end the combined purpose covers each subtype's purpose. A subpart with an objective purpose the parent cannot carry stays its own element. Combining never optimizes a functionality away.
- Why: Annealing keeps the root map minimal, coarse and shallow without discarding any functionality. A subtype exists only because it shares that join, so the join is where it lives.
- How it shows: Reading a join returns its combined purpose and function, and beneath them each subtype with its end and its own piece.
- Build: A subtype record has subtype id, join id, end which is provider or receiver, address, name, name_length, role, its own piece, relation, observation and refs. Its own piece is a function at the provider end and a purpose at the receiver end. The join record holds the combined purpose and combined function. Coverage is the intake agent's judgment and is never checked by the store.
- Acceptance:
  1. A join with two provider-end subtypes reads back with the combined function on the join and each subtype's own function, relation and observation under it, marked provider end.
  2. A receiver-end subtype reads back with its own purpose, marked receiver end.
- Relates to: MAP-031, MAP-032, MAP-040, STORE-011.
- Status: confirmed. The Canonical Intake response schema currently expresses only provider-end subtypes; see open question 2.

### MAP-031 A subtype is reachable only through its join and is never a root

- Requirement: A subtype is never a root element and never a join's receiver or provider, and it is reached only through the join that holds it.
- What this means: The absorbed element is not mapped to the external graph. It still keeps its own address, relation and specific purpose or encounter, and layers and memory attach to it directly by its subtype id.
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

- Requirement: An intake result is stored as elements, joins, refs and subtypes in the project's map layer, with nothing lost.
- What this means: The Canonical Intake response maps onto the records as follows. Two response forms exist: the 1.1 schema of `Canonical_Intake.xml`, and the test schema of `Canonical_Intake_test.xml`, which adds nested subtype joins. The mapping covers both.
  - The result id is kept on the intake layer written for that intake.
  - Each root `<element>` becomes an element with its address, name, name_length, role and refs.
  - Each `<join>` inside a root element becomes a join owned by that element, with its provider resolved by address, every field in MAP-020, and the refs written directly inside the join, which only the test schema has.
  - An `<element>` nested directly inside a `<join>`, as in the 1.1 schema, is the definition of that join's provider: its address equals the join's provider. It becomes, or adds to, the provider's element: when no element holds that address yet, one is created with the nested element's address, name, name_length, role and refs; when one exists in the intake layer being written, the existing element is kept, STORE-009, and the nested element's refs are added to it, STORE-012; when the existing element belongs to another layer that is locked, the nested element's refs are written onto the join that holds it, in order and unchanged, because a locked layer changes only by revision. A nested element whose address differs from its join's provider is recorded as written, as an element, and its join is not changed.
  - A `<join>` nested inside a `<join>`, as in the test schema, becomes a subtype of the outer join at the provider end: its own piece is the nested join's function, with its relation and observation, its address is the nested join's provider, and the `<element>` inside it gives the subtype's name, name_length, role and refs.
  - Each ref becomes a ref record on its owner, in order.
  - When the result has no element with role AUE, none is created. The artifact is still recorded by the project's target, MAP-041.

  The intake's instructions are delivered to the performing agent by name. The agent completes the whole method, annealing included through step 11, and then submits the final shape once through the intake module's `intake_submit` tool, or `metaform intake submit` on the CLI, BASE-039. Its inputs mirror the intake schema's fields, and the mapping above applies to them field for field. There is no record-by-record writing during the trace and no XML answer.
- Why: The map is only useful if everything the intake agent recorded can be read back exactly, and the intake agent's inference is the expensive part.
- How it shows: After an intake, every element, join, subtype and ref in the result is readable from the store.
- Build: `intake_submit` checks the submission's form and stores the whole mapping above as one intake layer, with its provenance record, LAYER-010, in one atomic write, STORE-024 and STORE-032. A submission with a form error writes nothing. So a half-written intake never exists, and the map appears whole or not at all.
- Acceptance:
  1. Storing a real intake result, such as the MGM map, then reading the project back yields the same set of root elements, joins with every field, subtypes with their ends and pieces, and refs in order.
  2. No subtype in the result appears as a root element after storing.
- Relates to: MAP-015, MAP-020, MAP-021, MAP-030, LAYER-001, LAYER-010, STORE-013, STORE-024, MCP-009.
- Status: the mapping of root elements, joins and refs is confirmed, and one atomic submission through `intake_submit` after the whole method is confirmed. The handling of the 1.1 nested provider element, of test-schema subtype joins, and of a missing AUE is recommended.

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
- What this means: The map records where each element lives in the artifact, through refs such as a path. A worker that must judge the artifact itself, such as an intake agent or a sighted critic, is given the project's target and the refs, and reads the real material. A Type's universal description is never a stand-in for looking at the artifact. The blind latent critic is the one deliberate exception: its role is to reason from the map alone, so it receives the map and not the artifact, and its layer's provenance records that it was blinded.
- Why: A map built or checked from names alone repeats whatever the names suggest, and the errors then look like the artifact's own. Keeping the source identity and the project with the evidence means every conclusion can be traced back to the material it came from.
- How it shows: The intake instructions a subagent reads name the project's target. Reading an element or a join returns its refs, so an agent can open the exact files or passages behind it.
- Build: Every element and join read returns its refs in order. The intake instructions served by name carry the project's target, filled into the intake text's `<target>` element, BASE-039. The project id is filled into the text only where the text holds a `{project_id}` placeholder; otherwise `intake_submit` stores into the folder's project, or the project named by its optional project argument, MCP-025. A workflow that gives a worker source evidence passes refs and the target, never a summary in their place. A blinded role receives map reads only, and its provenance record sets blinded to true.
- Acceptance:
  1. Reading a join returns its path refs exactly as written.
  2. The served intake instructions for a registered project contain that project's target type and value in the `<target>` element.
  3. `intake_submit` called with a project argument stores into that project, whatever the folder.
- Relates to: MAP-021, MAP-041, LAYER-010, LAYER-015, MCP-009, STORE-025.
- Status: confirmed.

## Open questions

1. Root Types: are the roots code, document, media, data and stakeholder as in Canonical Intake 1.1, or does asset replace media and entity or exterior replace stakeholder?
2. Receiver-end subtypes: the intake response schema has no place for a subtype that keeps its own purpose under a combined purpose. How should the intake express one?
3. Can a subtype be the receiver of joins of its own after annealing, or do its joins lift to the parent?
4. Can one element be a subtype in two different joins, such as one probe serving two failsafes?
5. May a subtype share an address with a root element of the same project?
6. When there are several VEs, is one recorded as primary, and how?
7. Roles within a join: are hard dependency, property and supportive recorded on joins, and how? That property joins carry transitivity in the map itself is settled, MAP-022.
8. May a subtype hold subtypes of its own?
9. Answered: the agent submits once through `intake_submit` after the whole method, MAP-040. Does the intake agent write its result as one whole submission or record by record through tool calls?
10. C(T) names the Type's single Encounter Function e, while each join stores the provider's function for that encounter. Does the Type record also store its one Encounter Function, and if so, who writes it?
11. May a join have the same element as receiver and provider?
12. Are Type records shared across projects, as MAP-010 recommends, or kept in each project store, as STORE-008 has them?
13. Must an element created by a layer other than the intake carry a role? MAP-017 requires exactly one role on every element; STORE-009 allows none.
14. When a project holds more than one AUE, how is the set of elements belonging to each AUE recorded? (MAP-042)
15. Answered: the intake text's response protocol will say to submit the final shape through `intake_submit`, with the method word for word, MAP-040. NEW The Canonical Intake text asks for an XML answer, while the intake is to be written through Metaform's tools. See chassis section question 9. (MAP-040)
16. NEW The Canonical Intake's reading examples disagree on the root `code`: `code.loop.main` reads as main loop program code, and `code.bus.data.event` as event data bus code. Does a root carry a reading phrase, such as program code for `code`, or does every root read as its own name? (MAP-012)
