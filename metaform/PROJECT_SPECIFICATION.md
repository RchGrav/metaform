# Metaform: project specification and agent guide

## 1. Title and specification status

**Document:** Metaform project specification and agent guide. **Date:** 2026-11-11. **Status:** Draft for the founder's correction.

**How this document is written.** It states the design and the reasoning that produces it. A rule appears with the reason it exists, so that a reader can work out a case the document does not list. It does not record who said what or when. Where a reason is not known, the document says so and does not invent one.

**Status marks.** Each consequential statement carries one mark.

| Mark | Meaning |
|---|---|
| **[R]** | Established requirement. |
| **[F]** | Established fact or description. Not necessarily required. |
| **[I]** | Interpretation: reasoned by an agent from the design and not confirmed. It binds no one. |
| **[U]** | Unknown or unresolved. |

**Basis.** The founder's explanations across working sessions from 2026-10-30 to 2026-11-11, read in full; the founder's intake procedure in its pure form and its earlier longer form; the founder's documents on mutation and on rendering language; the earlier Python system; and the repository on 2026-11-11.

## 2. Executive summary

An agent has a limited capacity for tracking and understanding. Working out what a project is uses that capacity before the task starts, and the task gets what is left. Metaform does that orientation once and keeps the result where every agent can read it at a glance. The saving is in reasoning. It is not in tokens or money, and Metaform does not make a model more able. [R]

- **What is kept is function, not material.** The map names what each part of an artifact does and for what purpose. Function outlives changes to files, and it exists in a photograph or a story as well as in software. [R]
- **The map is small on purpose.** It is a set of reference points. Knowledge attaches at those points as overlays. A deep map would spread knowledge away from the place an agent looks. [R]
- **The map is an inference.** Its value is that every agent reasons from the same reading. No reading is the correct one, so a map is never graded and an intake is never gated. [R]
- **Agents reach the map through one tool** whose definition is a list of operations under one kilobyte. Everything else arrives when it is needed. [R]
- **The system is extended by modules on an immutable chassis.** [R]
- **Three implementations serve one purpose:** Rust, Node and Python. [R]
- **A web interface lets a person see and move through the map.** An interface that meets the requirement does not exist yet. [F]

## 3. Purpose, scope, and intended use

**Purpose of this document.** To let a capable reader or an agent understand Metaform well enough to work on it, to leave unaltered what must not be altered, and to judge proposed work.

**In scope:** the map and its terms; the intake procedure; overlays; the MCP server and its tool; the chassis and its modules; the three implementations; the web interface.

**Related and out of scope.**

- **Mutation of artifacts.** A separate pipeline scores an artifact from the side of each party that relies on it and directs changes to it. It depends on Metaform for one thing: a thing must be understood as a type before it is changed, or the change may turn it into a different thing (section 6.2). The interface between that pipeline and this repository is not specified. [U]
- **Agents, messaging and tickets.** A later module owns agent identity and messages. Tickets hold knowledge that does not last; the map holds knowledge that does. Neither is a base mechanism of Metaform. [F]
- **The project named Topogee** is built with Metaform. Metaform is its own project and is not designed around any one project, including itself. [R]

**Intended users.** People who want to see what a project is and direct work on it. Agents that need to orient in a project and record what they learn.

## 4. Project intent and intake method

### 4.1 Intent

The map answers one question for an agent arriving in a project: what is this. An agent that has the answer does not spend its reasoning rebuilding it, and it does not act on a wrong guess about what a part is for. Most wrong or incomplete work by agents starts from that guess. [F]

### 4.2 Two things are called intake

1. **The intake procedure** infers a map from an artifact (section 6.4).
2. **The intake method below** is for an agent that must take in information about the Metaform project itself.

### 4.3 Intake method for project information

1. **Read the definitions first, and work answers out from them.** The glossary of the intake procedure contains the design for a reader who reasons from it. A question about the semantics is answered by derivation and brought to the founder as a reading to confirm. It is not brought as an open question. [R]
2. **Write the reasoning, not the words.** An explanation given in conversation is a way to reach understanding. Copying its sentences into a document, or into the procedure, keeps the words and loses the understanding. The result reads as a list of rules to obey, which is the failure this project exists to remove. [R]
3. **Find the current text before reading any.** Several versions of most documents exist, some rewritten by agents. [F]
4. **Read whole documents.** Summaries and headings have misled agents here. [F]
5. **Keep semantics and tooling apart.** The procedure's concepts, coined terms, definitions and examples are semantics. The server, schema, commands, stores and pages are tooling. Tooling is fitted to semantics. [R]
6. **Mark what you inferred.** A reading is marked [I] until it is confirmed.

## 5. Core design principles

1. **The semantics are load-bearing.** The procedure's terms and definitions were tuned by test over months, across models and artifact types. Some terms are coined and left slightly open, so that their meaning settles from the artifact in front of the model. A reworded definition is a different instruction and gives a different inference, and nothing in the text shows that it broke. Treat the text as a formula: use it or leave it, do not adjust it. [R]
2. **A rule comes with its reason.** A model given only a rule can obey it. A model given the reason can infer the next case, and it stops spending reasoning on ceremony. This holds for the procedure, for overlay definitions and for this document. [R]
3. **Function, not material.** Language, encoding, medium, genre and style are ways a function is carried. Naming them would split one function into several elements and tie the map to material that changes. [R]
4. **An inference, never graded or gated.** A check on what was inferred makes the agent satisfy the check. Checking the shape of a command is different and is permitted. [R]
5. **The base map is minimal.** It holds elements and their dependencies. Everything else is an overlay. A base that holds little stays stable while knowledge is added and removed around it. [R]
6. **Shallow and coarse.** Elements are reference points for the knowledge of a region. [R]
7. **Progressive discovery.** Nothing is presented before it is needed, and nothing that is not needed. Whatever is put in front of a model is paid for in reasoning whether it is used or not. [R]
8. **Correction teaches.** A wrong command is answered with the reason and the command that would be accepted. The moment of the error is the moment the shape is needed. [R]
9. **No logic without an observed failure.** A check, a gate or a step that fixes nothing observed is ceremony, and ceremony costs reasoning. [R]
10. **No ceremony in the tool.** An intake has no start and no stop. Data lives in one place and is shown as it is written. [R]
11. **The map grows; elements mutate.** A changed function is a different function and a new element (section 6.2). [R]
12. **Immutable core, modular extension.** Features arrive as modules and never change the chassis (section 6.6). [R]
13. **One purpose, three implementations.** [R]
14. **Own code.** No new dependencies and no copied libraries. Outside code is read for ideas. Code the project does not own is code it cannot keep small or correct. [R]
15. **Honest status.** Simulated behaviour is labelled. Unbuilt behaviour is not described as working. [R]
16. **Plain technical English** in project prose, with the project's terms and no invented ones. [R]

## 6. Concepts and architecture, including the web interface

### 6.1 The map

**Element.** A constituent part of an artifact, named as a type. Naming a type lets the model's existing knowledge of that type do the work; naming an instance would give it nothing to reason from. Being nameable does not make a part worth an element. [R]

**Address.** A dotted path that narrows from trunk to leaf. [R]

- Read in reverse, with spaces for periods, it is the element's ordinary name: `code.bus.data.event` is an event data bus in code. An agent that sees an address therefore needs no glossary.
- Each prefix is itself a complete type, and a child is a part or a functional kind of its parent. This is what lets knowledge placed at a prefix apply to everything beneath it.
- A segment names a functional approach. `code.engine.game.fps` is valid because a first-person view is a distinct functionality. `code.engine.game.platformer` is not, because it names the challenge of a game and not a technical function. A product name, a language or an encoding is never a segment.
- The address is the identity. Knowledge is bound to the address where it was inferred. If the address changes, the knowledge is inferred again and is not carried across.

**Base types.** Four roots name what an artifact is made of: `code`, `document`, `media`, `data`. They are always local to the artifact being examined. [R]

**Outside the artifact.** Two more roots hold what is not part of the artifact: `upstream` for what it relies on, and `downstream` for any who or what that relies on it. They exist so that an element the artifact relies on, or one that relies on it, is never mistaken for one of its parts. [R]

- An outside artifact is one whole thing seen from here. What names a whole artifact as a type is its Defining Element, so its address is `upstream` or `downstream` followed by the address of its own Defining Element. A game engine the project requires is `upstream.code.engine.game`, and the entry can refer to the project that supplies it. [R]
- A downstream who is not an artifact. It is addressed by the type of party it is. [R]
- Outside elements are not in the project's tree. They carry no role and do not inherit the project's overlays. A dependency on something upstream is still held locally and points at the local upstream entry. [R]

**An internal root** holds overlay definitions (section 6.3). The intake procedure does not use it, because an intake finds no overlays in an artifact. [R] The build also accepts a root named `collection`, which is not one of these roots. [F]

**Roles.** Each element inside the artifact has one. [R]

| Role | Meaning |
|---|---|
| Definitive | The element whose loss would stop the artifact from being the same type. Its function sums up the combined result of the artifact. There is exactly one. |
| Supportive | An element so entangled with what the Definitive element delivers that the artifact would not be the same type without it. The role states the coupling, so no separate field for coupling is needed. |
| Notable | An element that states an essential demand: what the artifact expects, needs or depends on to operate. |

There are three roles. A fourth, Divergent, was dropped. The build, the schema and the tool contract still accept it, which is a departure from the design. [F]

**Not in the map.** A parametric quality can be tuned and is not named in artifacts of the type, so it has no address. [R]

**Fields in the build.** `technical_name` (the address words in reverse, which the server can check against the address), `name` (the ordinary name), `role`, `uri`, an optional `status`, dependencies and overlay records. [F] Stored keys are lower camel case and agents see snake case, so that neither side carries the other's convention. Anything keyed by a unique name is a dictionary. The answer to a query is a bare array. [R]

### 6.2 The dependency

A **dependency** is the record an element keeps about one element it relies on. The other element's address is the dependency. The record holds three things. [R]

| Part | The procedure's term | Meaning |
|---|---|---|
| Purpose | Operative Purpose | The why: the active goal the receiving element holds. It belongs to the receiver. Everything specific to this one artifact is confined to it. |
| Function | Encounter Function | The how: what the providing element does, in this meeting, that satisfies the purpose. |
| Direction | | Which way the substance moves, seen from the holder: inbound, outbound or two-way. |

- **The record lives in the receiver.** The function belongs to the provider, but one provider serves different receivers in different ways. A function stored on the provider would have to be one statement for all of them. Stored in each receiver's record, it is exact for that meeting. [R]
- **Direction is of the substance, never of the request.** Every dependency begins with a request, so the direction of the request says nothing. [R]
- **A function is only a how until a receiver holds a why for it.** This one fact produces the rest of this section. [R]
- **The downstream is the receiver of the whole artifact.** The Definitive element's function sums up the artifact, and nothing inside the artifact can be the receiver of that. The downstream entry holds the purpose for it. That purpose is what makes a map of types specific to this artifact, and every purpose inside the artifact exists to deliver what the downstream encounters. [R]
- **The downstream is inferred, not found.** It is not present in the artifact. The procedure's term for it is defined so that the model reasons past the answers that fit every artifact: the user, the developer, the operator. Those identify nothing about this one. A downstream is who or what has an interest that drives the artifact to be better, and it may be a thing: the projects that use a software kit are downstream of the kit. The term is for the intake only. It is not a role and never appears in an address or in front of a person. [R]
- **How many downstreams.** One for each unique interest or dependency in the artifact. Each is a different purpose and so a different why to trace through the artifact. The same interest held by another is the same purpose and the same record, and it adds nothing to reason about. So the count required and the count allowed are the same number. [R]
- **Type understanding and the frozen core.** To understand an element as a type is to hold three things together: the receiver with its why, the provider with its how, and the element itself. The set of those relations for an element is its core. Work on an element may mutate it: change how it does what it does. Work that changes what it does has transformed it into a different element, and the map grows by one. Nothing stores the core as a field. The protection is the understanding the intake recorded. [R] The reading of the formula's three terms as receiver, provider and element is an agent's. [I]
- **The record is itself an overlay,** in a reserved group that is not listed with the others and cannot be deleted, because it is the map. [R]

**Names in the build.** The record is stored as `wants`, with fields `why`, `how` and `direction`. The name dependency is decided and not applied. The plain field names were chosen so that agents reading a map need not learn the intake's terms, with the procedure saying which concept is recorded in which field. That arrangement has not been tested, because the procedure in the repository removed the concepts. [F] [U]

### 6.3 Overlays

An **overlay** is one kind of knowledge spread across the map at the places where it applies. It adds to the map and does not change it. [R]

- **Why overlays.** Everything that is not function still has to live somewhere: the language of the code, the insights for a port, memories, skills, sources. In the base map it would make the map deep and unstable. As overlays it can be added for a piece of work and removed when the work ends, and the map is the same before and after. [R]
- **Definition.** An overlay is defined beneath the internal root, and the definition may sit several segments down. Being defined is what permits its records to be written. The definition is the overlay's schema and the complete validation of its records. It holds a description, an instruction, the fields and a template. Each field has a part of speech, a rule and an example. The template is one sentence that the fields fill, and it must read correctly. [R]
- **Why the definition is in the map.** The number of overlays has no limit, so their schemas cannot be delivered in advance. An agent reads a definition when it goes to write that overlay. [R]
- **Why a sentence and parts of speech.** Records are read by agents as language. A record whose fields fill a correct sentence can be delivered as that sentence, and the program never has to repair grammar. [R]
- **Reach.** An overlay is linked at an element and applies there and beneath, because what is true of a type is true of its kinds and parts. It never applies upward. A mask at an element stops it from there down, which is how knowledge is removed from one region without deleting it. Along the path from the root, an overlay continues if it arrived and is not masked, or if it is linked at that step. Defining an overlay does not turn it on: the project's list of enabled overlays does. [R: not built]
- **Arrays on an element.** `overlays` for those linked there and `masked_overlays` for those masked there. [R: the build still uses the earlier names.]
- **System overlays,** shared by every project. [R]
  - *Memory.* Each address has its own memory graph. An agent reads and writes it only while at that address, so a memory is always about the place it was made.
  - *Skills.* An agent at an address is told that a skill exists there by its front matter, and opens it only if the task needs it.
  - *Sources.* Links to entry points in the material. A source stays at the one element it was linked to and is never inherited, because a link to a place in a file is true of one element only.

### 6.4 The intake procedure, decomposed

The intake procedure infers the base map from an artifact. It is the founder's text, held unaltered at `metaform/intake/pure_intake.xml`. This section explains why each part of it is there. It is an explanation for people who work on the project. It is not a substitute for the text, and an agent performing an intake is given the text. [R]

**What the procedure is designed against.** Asked to describe a project, a model lists what it can see: files, classes, functions. That list is long, it changes with every commit, and it says nothing about why any part exists. Every part of the procedure works to turn the model away from that list. [I]

**The definitions do the work.** [I, reasoned from the text]

- *Element* is defined with a warning attached: a part can be named and still not deserve attention. This removes the inventory at its source.
- *Notable* is defined by demand: an element is notable because it states what something expects, needs or depends on. So an element earns its place through a dependency, not through existing.
- *Receiving* and *Providing* are positions in one dependency, not kinds of element. The same element receives in one record and provides in another. This is why the trace can walk: each provider becomes the next receiver.
- *Operative Purpose* is an active goal held by the receiver. *Encounter Function* is how the provider is encountered, used or experienced. The second term is left open so that it fits what the artifact is: an interface in software, an effect on a viewer in a photograph, a turn of plot in a story. A tighter term would fit one kind of artifact and fail the others.
- *Defining Element* is found by a test of loss: remove it and the artifact is no longer the same type. A test can be applied to anything, where a description would need to be rewritten for each kind of artifact. Its function is stated independently of medium, encoding, genre and style, so two artifacts that do the same thing get the same Defining Element whatever they are made of.
- *Supportive* uses the same test of loss, applied to entanglement with the Defining Element.
- *Parametric* separates what can be tuned from what can be mutated. A brightness or a buffer size has no name of its own in artifacts of the type, so it gets no address, and tuning it is never a change of function.

**The namespace rules** make each name checkable by reading it. If the reversed address does not read as a well-understood name, the element is wrong. The valid and invalid examples sit in pairs that differ by one thing, so the model learns the boundary and not a list: a first-person view is a function and a platformer is not; a photo is a medium and a JPEG is an encoding. [I]

**The method, step by step.** [F as to the steps; I as to the reasons]

| Steps | What the agent does | Why |
|---|---|---|
| 1 | Takes the Defining Element as the first receiver and asks what it requires of other elements. | The Defining Element is what the artifact is. Everything the artifact needs, it needs in order to deliver that. Starting there means the trace reaches only what matters, and an element that no purpose reaches has no claim to be in the map. |
| 2 | For each element whose function serves a purpose, writes a record in the receiver with the purpose and the provider's address. | The purpose belongs to the receiver (section 6.2). |
| 3 to 5 | Moves to each provider, treats it as a receiver, and repeats, until no purpose is unmet and no notable element needed to understand the artifact is unnamed. | The stopping rule is understanding, not exhaustion. The trace is driven by demand, so it ends by itself where demand ends. |
| 6 to 8 | Combines elements where the shape can be reduced without losing the categorical understanding, only when they can share one dependency, under a name that obeys the namespace rules. | The trace finds specifics; the map needs types. Two elements that can share one dependency are, to their receiver, one thing. The naming rule keeps a combined element a real type and not a bucket. |
| 9 and 10 | Keeps what was combined away, and lists those parts as subtypes: full addresses beneath the element they were combined into. | Knowledge about a specific part still needs a place to attach. The subtypes are not in the map, so the map stays coarse, and their addresses remain valid. |

**The constraints hold a balance.** One says to name an element at its most specific reusable type and never with a vague label. Another says to combine and keep the shape coarse. Together they fix the level: specific enough to be a real mechanism, general enough to be reused in another artifact of the type. A third constraint makes that possible: everything particular to this one artifact is confined to the purpose. Elements are types; the purposes are what make the map this artifact's. [I]

**The goal statement says the operation is shallow, and says so twice.** It names the harm directly: a deep intake moves knowledge away from the place an agent addresses. The map is a base to extend, not a description to complete. [R]

**What the pure text does not cover, and how each gap is filled.**

1. *Outside the artifact.* The text defines four base types and nothing for what the artifact relies on or what relies on it. The gap fill is at `metaform/intake/intake.proposed.xml`. It adds the downstream concept and its examples from the founder's earlier text, definitions of upstream and downstream with their reasons, the two roots and one example. It adds lines and alters none, and its reasoning is confirmed. The method needs no new step: the downstream entry is a receiver, the Defining Element is its provider, and step 1 already begins there. [F]
2. *Where the result goes.* The text ends by returning one XML document. In this system the result is written to the map through the tool. That difference is tooling, and it is settled without touching the text: the server gives the agent the procedure, and a separate tooling note, outside the procedure, says how each part of the result is written. The procedure that agents are given today did the opposite. It merged the tool's commands into the text and removed the concepts, and the maps it produced were inventories of code. [I]
3. *Where the function is recorded.* In the text's result each element states its own function, and each join carries the purpose. The map stores the function in the receiver's record. The two agree: the element's function is what it does as a type, and the record keeps that function as it applies to one meeting. The tooling note states the mapping. [I]
4. *What the join carries beyond the purpose.* The text's join also holds a relation, an observation, references and the combined parts. The base map holds purpose, function and direction only, so those four are written as overlays. [I]

**What follows for the build.** The text agents are given should be the pure text with the gap fill, delivered by the server, with a tooling note beside it and nothing merged into it. Until that is so, an intake run in this repository is not evidence about the procedure. One agent performs an intake. [I as to the arrangement; R as to one agent]

### 6.5 Storage and the three implementations

- **Agents see whole elements; the store keeps fields apart.** Reasoning is easier over an element with its fields together. A store by field is faster to query, and a new overlay is a new table and not a change to every element. Both are required of all three implementations. [R]
- **One core database lists the projects. Each project has its own database,** with the same name in every project, in a folder named from the project's path. Only databases in use are open. Nothing is written into the project's own folder. [R]
- **Writes are queued, with fair queuing,** because several agents write at once and one process is the only writer. [R]
- **The home folder is `~/.metaform`.** [R]

| Implementation | Why it exists | Store |
|---|---|---|
| Rust | The modern form. A map is a graph, and a graph database stores it as one. | Graph database, one server process for each home folder. |
| Node | The MCP ecosystem develops in this language first. | SQLite. |
| Python | No compiled code, and the language people most easily extend. | SQLite. |

A conformance suite sends the same commands to all three and compares the answers. [F] The Node form was first made quickly and without concurrency; that first form is not the design. [R]

### 6.6 The chassis and its modules

The chassis is the fixed core. It tracks projects across the machine, and it is the one entry point for extending the system. [R]

- **Immutable.** It owns the data, the settings and the database, and it is driven by events. A feature never changes it. If features could change the core, each feature would put every other feature at risk. [R]
- **Everything else is a module,** the MCP server included. The chassis is complete with every module absent. [R]
- **The template rule.** Anything the chassis exposes to a module is defined, placed in a template module and documented, and nothing is exposed before all three. A module author then has one complete, true statement of the contract, and the chassis has no undeclared surface for a module to lean on. The earlier Python system stayed stable for months of added features under this rule. [R]
- **The storage boundary.** A module declares its tables and reaches them only through the chassis. A module with its own database connection can break the single writer and the queue. [R]
- **A module adds operations, not tools.** In the earlier system each module command became a tool, and the tool list passed 150 tools and 128,000 bytes that every agent received before its first call. It destroyed the thing the system exists for. A module's operations go under one tool, and a module may add operations under another module's tool. [R]
- **Tools and the command line.** A tool operation may be used at the command line. The reverse does not hold: the tool reads and writes data, and commands such as export stay out of it. Command-line commands are hierarchical: the module, then the command. [R]
- **Settings.** Everything works with no switch set. A switch may be set and saved in place of a long command line. A reset returns to the defaults. A glued setting survives a reset. Defaults are declared in code and never stored. [R]
- **The MCP server with and without a chassis.** The server works alone. When a chassis is present the server finds it at startup and uses it as the source for the data the two share. [R]

**State today.** The Rust form has a registry of projects, settings and a write queue. None of the three has the module entry point, the template module or the settings pattern. [F]

**Unresolved.** The language of the chassis and whether it is part of the MCP server. How one module contract serves three languages. Whether one module may call another directly. [U]

### 6.7 The web interface as a concept

The web interface is where a person sees the map and moves through it. Section 7 treats it.

## 7. Web interface: navigable surface and base requirements

"Base navigable surface" is used here for the part of the interface that every use of it shares: the map and the means of moving through it.

### 7.1 Purpose

A person uses the interface to explore the functional design of a project. The map is the work surface. It is not a dashboard, and the picture is a means to understanding and not the product. [R]

### 7.2 What is required of the new interface

- **Original, from an empty page.** Two pages exist and neither is the base. One was rejected. The other, a port of an earlier page, is heavy on the processor and built around visual effects. [R]
- **Legible first.** A person must be able to read every name and follow every line. Effects that cost legibility or processor time are not wanted. [R]
- **A designed system of easing and zooming.** Movement is how a person keeps their place in a map larger than the screen. It has to be intuitive and smooth, and consistent enough that a person learns it once. A sibling project's map viewer is the nearest example of the feel. [R]
- **Improved by iteration,** one thing at a time. [R]

### 7.3 The base surface

**Live.** The page follows the database continually and never needs a reload, because an intake has no start or stop and the map is simply what is stored. Changes are pushed when a command is applied; the page does not poll. New activity is marked and never moves the view or takes focus, because the person's place in the map is theirs. [R]

**Moving through the map.** [R]
- Pan and zoom are smooth and predictable, with zoom in, zoom out and fit.
- A click on a box selects it and zooms to it and its direct connections.
- A double click moves into an element's nested content.
- Every narrowing has a visible way back.
- Elements are nested boxes that fold and unfold, and a folded box is distinguishable from an empty one.
- Layout is automatic, in the manner of a flowchart, from the project's own layout code.
- Keys drive views: one shows one feature at a time, one zooms through levels, one starts a tour, and `?` lists the keys.

**What is drawn.** [R]
- Lines show the direction in which substance moves, as recorded.
- Lines turn at right angles. Curved lines could not be followed.
- Names have room to be read. [F: intended; how is not settled.]
- Purpose, function and direction appear in plain words. The intake's abbreviations never face a person.

**Identity and frame.** The project, the map's title, the path and the zoom level are visible. Persistent controls are few. The interface is dark first and desktop first. [R]

**Projects.** One interface serves every registered project. A person can switch projects and follow a link from one to another, with a way back. [R]

**Overlays.** A person can show, hide and isolate each overlay, and the controls say what they do in the system's terms. [R]

**Agents.** Presence is shown quietly: who, in what state, where. [R]

**Entry.** The command that starts the interface prints its address, and the server tells agents to give that address to the person. [R]

**Honesty.** No inert control. No feature added for the look of completeness. Simulated data is labelled. [R]

### 7.4 What exists

A rejected page at the host's root, and the port at `/classic/`. The host lists projects, forwards reads, forwards writes that come from the page's own address, streams change events and serves files. [F]

### 7.5 Not settled

- **Technology.** Recommendation: plain TypeScript with no framework, drawing to SVG or canvas, with the project's own layout and motion code. This follows from principle 14 and from the weight of the earlier page. [I]
- **The rules of motion.** They are the agent's to design and propose, and the founder's to accept. [U]
- **Views of a written specification** (a structured view, a Markdown document, proposals from agents) were required of an earlier design. Whether they belong to the base or to a module is not settled. [U]

## 8. Reuse of the base surface by another project

- The system is extended through the chassis and its modules. In the earlier system a module declared its own panels and toolbar items, and the interface placed them. [F]
- By that pattern, reuse of the base surface means: the base is fixed, and another project's module adds to it by declaration, as it adds operations to a tool. [I]
- For this to work the base must not assume Metaform's own modules, any one project's content, or whether its data is real. [I]

**Unresolved.** Whether this is what reuse means. What a module may declare for the interface. Whether the interface is itself a module. [U]

## 9. Feature overlays within the base surface

- A feature overlay is a map overlay that tags the elements making up each feature of a project. [R]
- The interface navigates by it: one key shows one feature at a time, and the tour goes feature by feature and then one function at a time. [R]
- So an overlay, in the interface, selects what the base surface shows and in what order. It does not add panels or replace navigation. [I]
- An overlay is available in the interface where it is enabled and not masked. Isolating one shows its elements and dims the rest. Two overlays cannot conflict, because neither changes the map. [I]

**Unresolved.** Whether an overlay may bring its own view. The order of a tour. [U]

## 10. MCP server

- The server is how agents read and write a project's map. It offers one tool. [R]
- It keeps no intake session: no start, no stop, no lock. [R]
- Its instructions tell an agent to give the person the interface's address after an intake or a change to the map. [R]
- It handles the intake procedure. [R] Reasoned form: the server offers the procedure as a prompt, which a person or an orchestrating agent selects, with the tooling note of section 6.4 beside it. A prompt costs nothing until it is selected, and selecting it starts nothing in the server, so it obeys progressive discovery and the rule against ceremony. [I]
- As built: it sends one instruction at connection, lists one tool and one resource, and announces changes. It does not deliver the procedure. [F]

## 11. Tooling model and progressive discovery

### 11.1 The tool

One tool. Its input is one object with one key: an operation or an address. A write is the stored form of an element under one key, so there is one shape to learn. [R]

| Operation | What it does |
|---|---|
| add, update, delete | Write. |
| an address | Read one element's own content. |
| a key that starts with a period | Return the stored form beneath that path. |
| map | Return the shape alone: addresses and dependencies. |
| orphaned | List elements nothing relies on. |
| goto | Place the agent at an address and return a summary of what is there. |
| search | Match anything in the map; answer with the address and the overlay. Not built. |
| help | Return the form of help, or of one named thing. One level for each answer. |

### 11.2 Progressive discovery

1. At connection an agent receives the tool's name and its list of operations: 672 bytes in the build. An agent that never writes pays for nothing else.
2. An agent that wants a shape asks help. Each answer names what can be asked next.
3. An agent that sends a wrong command receives the reason and the accepted command.
4. An overlay's definition is read when the agent goes to write that overlay.

**Validation** covers the shape and integrity of a command. It never judges what an intake inferred. [R]

**Departures in the build.** Two refusals return no usable command. `search` is absent. [F]

## 12. Task-relevant context and information boundaries

- **Context is selected by address.** Knowledge is attached where it applies, so being at an address is the query. This is delivery, not search. [R]
- **Arrival gives a summary.** Who relies on the address, what it relies on, the overlays there, the front matter of skills, and counts of records. The agent opens what the task needs. Sending the records themselves would spend the agent's reasoning on material it may not use. [R]
- **Delivered once.** A later arrival in the same context returns only what changed. [R]
- **By ticket as well.** A ticket tied to an element orients the agent as arrival does. Without tickets, an agent is told to locate the function in the map before working on a part of the system. [F]

**Reducing context is not withholding.** What an agent needs to act correctly is never omitted: a refusal always carries its correction, the shape of any command can always be asked for, and a delete that would leave a dependency pointing at nothing is refused with the command that removes the dependency first. [R]

## 13. End-to-end workflow

Illustrative only.

1. A person starts the interface; the command prints an address.
2. An agent connects and receives the short tool definition.
3. The agent reads the shape of the map and knows what the project is.
4. The agent goes to the element its task concerns and receives the summary there.
5. To write, the agent asks help or sends its best attempt; a wrong attempt returns the right command.
6. The server announces the change. The open page marks the element and does not move.
7. The person clicks the element, reads its purpose, function and direction, moves in, and comes back.

For a piece of work, an overlay is linked where the work applies and removed when it ends. The map is unchanged.

## 14. Updating and maintaining the project understanding

- A settled matter is written into the specification with its reason. A question stays a question until the founder decides it. [R]
- The intake procedure and its semantics change only on the founder's direct instruction. Tooling may be made more efficient. [R]
- Text proposed for the procedure is written with its reason, is shown before it is placed, and adds to the founder's text without altering it. [R]
- A rename is applied in one pass across tooling, and each place it could not be applied is reported. [I]
- Preserved source material and the founder's own folder are read and not edited. [R]

## 15. Building from and evaluating work against this specification

**Method.** State what the work changes. List the requirements it touches. Classify it: **compliant** when every touched requirement is met; **non-compliant** when one is broken; **indeterminate** when the outcome depends on something unresolved. An interpretation is never counted as a requirement.

| Proposed work | Finding | Reason |
|---|---|---|
| Reword a definition in the procedure to make it clearer | Non-compliant | Principle 1. |
| Add a sentence to the procedure that states a rule without its reason | Non-compliant | Principle 2. |
| Merge the tool's commands into the procedure's text | Non-compliant | Section 6.4. |
| Add a check that refuses a purpose for its wording | Non-compliant | Principle 4. |
| Tell intake agents to record more elements | Non-compliant | Principle 6. |
| Add an operation that starts or ends an intake | Non-compliant | Principle 10. |
| Add a check with no observed failure behind it | Non-compliant | Principle 9. |
| Give each command of a new module its own tool | Non-compliant | Section 6.6. |
| Let a module open the database itself | Non-compliant | Section 6.6. |
| Port an earlier page as the interface | Non-compliant | Section 7.2. |
| Copy an outside library into the repository | Non-compliant | Principle 14. |
| Put the intake's term for a downstream into an address | Non-compliant | Section 6.2. |
| Publish the list of operations in place of the full schema | Compliant | Principle 7. |
| Define an overlay several segments beneath the internal root | Compliant | Section 6.3. |
| Use the feature overlay to show one feature at a time | Compliant | Section 9. |
| Let a module add a panel to the interface | Indeterminate | Section 8. |

## 16. Canonical terminology and glossary

| Term | Meaning | Not to be confused with |
|---|---|---|
| Metaform | The project, and a map made by it. | A map of code. |
| Artifact | The thing examined: software, a photograph, a contract, a story. | |
| Element | A constituent part, named as a type. | A file, function or class. |
| Address | The dotted name of an element. | A file path. |
| Dependency | The record a receiver keeps about a provider. | An imported package. |
| Operative Purpose | The why, held by the receiver. | The purpose of the project. |
| Encounter Function | The how, of the provider in this meeting. | The element's function in general. |
| Receiving Element, Providing Element | The two ends of a dependency. | Roles. They are not roles. |
| Definitive, Supportive, Notable | The three roles (section 6.1). | |
| Upstream, downstream | What the artifact relies on; who or what relies on it. | Parts of the artifact. |
| Overlay | One kind of knowledge spread across the map. | A panel in the interface. |
| Mask | A stop on an overlay at an element and beneath. | Deletion. |
| Link | To attach an overlay at an element. | |
| Progressive discovery | Section 11.2. | |
| Chassis, module, template module | Section 6.6. | |
| Glue | To make a setting survive a reset. | |
| Mutation, transformation | A change in how; a change in what. | |

**Names in transition.** The build stores `wants`, `layer`, `layers` and `blocked_layers`. The decided names are dependency, overlay, `overlays` and `masked_overlays`. Earlier texts say join and purpose record for the dependency, and DE, SE and NE for the first three roles.

**Avoid.** "Refine" for adding function to a map: the map grows. "Topogee map" for a map: a map is a metaform. "Owner" for the person who directs the project: the term is founder.

## 17. Requirements and behavioral expectations

**Semantics**
1. Do not alter the intake procedure's terms, definitions or examples.
2. Text proposed for the procedure gives its reason and alters nothing.
3. Do not gate or grade.
4. The base map holds elements and dependencies only.
5. Keep the map shallow and coarse.
6. Keep tooling instructions out of the procedure's text.

**Tool and server**
7. One tool, a list of operations, under one kilobyte.
8. Present nothing before it is needed and nothing unneeded.
9. Answer a wrong command with the reason and the accepted command.
10. No start or stop for an intake.
11. Arrival returns a summary: front matter and counts.
12. An overlay's definition is its schema and its complete validation.

**Implementations and chassis**
13. Rust, Node and Python serve one purpose.
14. Agents see whole elements; stores keep fields apart; writes are queued.
15. The chassis is immutable and complete without modules.
16. Whatever the chassis exposes is in the template module and documented.
17. A module reaches storage through the chassis and adds operations, not tools.
18. Settings work with none set, and support set, reset and glue.

**Web interface**
19. Original, legible, with a designed system of easing and zooming.
20. Follows the database live; never moves the view on a change.
21. A way back from every narrowing.
22. Direction on screen matches the record; plain words for a person.
23. No inert control; nothing copied in from outside.

**Working practice**
24. Reason from the definitions before asking.
25. Write the reasoning, not the words.
26. Match every claim of status to its evidence.

## 18. Open questions, ambiguities, and decisions needed

**Readings to confirm.** Each is reasoned in the section named and is being built on unless corrected.
1. The arrangement for giving agents the procedure: the pure text with the gap fill, delivered by the server as a prompt, with a tooling note beside it and nothing merged in (6.4, 10).
2. The four things the pure text's join carries beyond the purpose are written as overlays (6.4).
3. The three terms of the frozen core are receiver, provider and element (6.2).
4. Reuse of the interface means modules adding to a fixed base by declaration (8).
5. A feature overlay selects what the base surface shows; it adds no panel (9).
6. The new interface is plain TypeScript with the project's own layout and motion code (7.5).

**Decisions that are the founder's.**
7. When the decided names are applied to the tooling, and whether the internal root is renamed with the overlay.
8. Whether the root `collection` is removed from the build.
9. Whether the stored field names stay plain. One intake each way on the same artifact and model would show the effect.

**Not yet reasoned or decided.**
10. The language of the chassis, and how one module contract serves three languages.
11. Whether a module may call another directly.
12. The interface between this repository and the mutation pipeline.
13. Whether a count of zero appears in an arrival summary.
