# Metaform: project specification and agent guide

## 1. Title and specification status

**Document:** Metaform project specification and agent guide.
**Date:** 2026-11-11. **Status:** Draft for the owner's correction. It is not definitive: section 18 lists material questions that are open.

**Evidence base.** The owner's statements in working sessions from 2026-11-09 to 2026-11-11; the owner's documents (an intake procedure, a mutation framework, a semantic compilation guide, a judge module contract, a one-page query design, two interface requirement texts, an architecture note for the wider system); and the state of the repository on 2026-11-11.

**Status marks.** Each consequential statement carries one mark.

| Mark | Meaning |
|---|---|
| **[R]** | Established requirement: the owner required it. |
| **[F]** | Established fact or description: stated or consistently observed, not necessarily required. |
| **[I]** | Conservative interpretation: a cautious inference or a recommended practice. It binds no one. |
| **[U]** | Unknown or unresolved: not established, in conflict, or waiting for a decision. |

**Limits.** The owner corrected the agents' reading of this project several times during the sessions this document draws on. Statements marked [I] are the most likely to be wrong. The owner's own wording governs wherever it differs from this document.

## 2. Executive summary

Metaform keeps a small map of what a project does, so that an agent can orient itself without spending its limited reasoning on working out what the project is. [F]

- The map is a set of elements at dotted addresses. Each element records what it relies on, for what purpose, and how the other element serves that purpose. [F]
- The map describes functionality, not files or code. It is an inference, and it is never graded. [R]
- Knowledge about the project attaches to elements as overlays: named kinds of records laid over the map without changing it. [R]
- Agents reach the map through one tool on a Model Context Protocol (MCP) server. The tool's definition is to stay well under one kilobyte and holds a list of operations. [R]
- Every answer follows progressive discovery: nothing is delivered before it is needed, and nothing that is not needed. [R]
- A wrong command is answered with the reason and the command that would be accepted. That correction is how an agent learns a command's shape. [R]
- The tool exists in Rust, Node and Python. The three serve the same purpose under one requirement. The Rust version is to take a more modern approach than the other two. [R]
- A web interface lets a person see and move through the map. The owner requires an original interface, written from scratch, that is legible and dynamic, with a designed system of easing and zooming. No interface that meets this exists yet. [R] [F]

The largest unresolved matters are: which text is the current intake procedure; what the web interface's reuse by another project and its feature overlays require; and how the server delivers the intake procedure. [U]

## 3. Purpose, scope, and intended use

**Purpose of this document.** To give a technically capable reader, or an agent, enough to understand Metaform, to work on it without altering what must not be altered, and to judge proposed work against what the owner has established.

**In scope:** the map and its terms; the MCP server and its one tool; progressive discovery and task-relevant context; overlays; the three implementations; the web interface.

**Out of scope, named for context only:**

- A pipeline that uses a map to score an artifact from each consumer's side and to change it under rules (stages named intake, score, mutation instruction, weight decay and export, with an optional judge stage). [F] How that pipeline connects to this repository is not established. [U]
- A wider architecture in which specialised roles prepare an agent's context and a harness controls agent sessions. [F] Its relation to this repository is not established. [U]
- A separate multi-agent discussion tool kept in the same repository. [F]

**Intended users.** People who want to see what a project is and to direct work on it; agents that need to orient in a project and record what they learn. [F]

## 4. Project intent and intake method

### 4.1 Intent

- The cost Metaform saves is a reasoning cost. An agent has a limited capacity for tracking and understanding. Orientation in a project draws on that capacity. Metaform does the orientation once and keeps the result. [F]
- Metaform does not raise a model's ability. It preserves the capacity that lets the model perform well. [F]
- The saving is not measured in tokens or money. A document that claims otherwise misstates the project. [R]
- The map answers one question at a glance: what is this project. [F]
- The map is also the footing for further uses the owner plans, across artifact types that include software, photographs, stories and scripts. Those uses are not specified here. [F] [U]

### 4.2 Two different things are called intake

1. **The intake procedure** is a project concept: the procedure by which an agent infers a map from an artifact (section 6.4).
2. **The intake method of this section** is guidance for an agent that must take in information about the Metaform project itself, to maintain this specification or to prepare work.

### 4.3 Intake method for project information [I, except where marked]

1. **Find the current source before reading any.** Several versions of most documents exist, including rewrites made by agents. Ask the owner which text is current. Do not assume the copy in the repository is. [R: the owner stated that the repository's procedure is an old one and not the current one.]
2. **Read whole documents.** Headings and summaries have misled agents on this project. [F]
3. **Extract, for each source:** goals; scope; requirements; constraints; actors; components and how they relate; terms with their exact spelling; details of the web surface; what is said about reuse and extension; rules for selecting context; overlays; open questions.
4. **Mark each extracted statement** with one of the four statuses in section 1.
5. **Record the reason with the rule.** The owner asks to be interpreted correctly, with the reason, and not to be quoted. A rule without its reason has been misapplied more than once. [R]
6. **Separate the owner's semantics from tooling.** The intake procedure's concepts, coined terms, definitions and examples are the owner's semantics. The server, schema, commands, stores and pages are tooling. [R]
7. **Ask when two sources conflict or a term is missing.** Do not settle a conflict silently. [R]
8. **Clarification is necessary** before any work that would touch the semantics, choose between versions of a text, name something, or define the reuse or overlay behaviour of the web interface.

## 5. Core design principles

1. **The semantics are load-bearing.** Treat the intake procedure's concepts and terms like mathematical formulas. Do not rename, reword, reorder, merge or add rules to them. Tooling is made to fit them. [R]
2. **Functionality, not material.** The map names what an artifact does. It leaves out language, encoding, medium, genre and style. [R]
3. **An inference, not a measurement.** No map is the correct one. A map made by a different model is a different valid reading. A map is never graded. [R]
4. **Never gated or judged.** The intake procedure is not blocked or scored by the tool. Checking the shape of a command is permitted; judging what was inferred is not. [R]
5. **Shallow and coarse.** The map is a light surface of reference points. A deep intake harms the project, because it moves knowledge away from where an agent will look for it. [R]
6. **Progressive discovery.** No information before it is needed, and none that is not needed. [R]
7. **The tool surface is small.** Well under one kilobyte, with a list of operations. [R]
8. **Correction teaches.** A wrong command is answered with the correct shape. [R]
9. **One purpose, three implementations.** Rust, Node and Python serve the same purpose under one requirement; Rust takes the more modern approach. [R]
10. **Honest labelling.** Simulated behaviour is labelled as simulated. Unbuilt behaviour is not described as working. [R]
11. **Plain technical English** for project prose, with the project's own terms and no invented ones. [R]
12. **Own code.** No new dependencies; outside code may be read for ideas and then written anew. [R]

## 6. Concepts and architecture, including the web interface

### 6.1 The map

- An **element** is a functional part of an artifact, named as a type. [F]
- An **address** is a dotted path from general to specific. Read in reverse it is the element's ordinary name. Each prefix is itself a complete type. A segment never names a language, an encoding, a genre or a particular product. [R]
- **Roots.** Four roots hold what is inside the artifact: code, document, media, data. Two more hold what is outside it: upstream, for what it relies on, and downstream, for the parties that rely on it. One further root is internal and holds overlay definitions. [R] The repository's code and one procedure text also list a root named collection; the owner's count of roots does not include it. [U]
- **Roles.** Each element inside the artifact has one of four roles: Definitive, Supportive, Notable, Divergent. One element is Definitive. [F] Earlier texts name the roles by the abbreviations DE, SE and NE, and expand SE in two ways (section 16). [U] Whether an outside party carries a role is not settled. [U]
- **Element fields in the build:** `technical_name`, `name`, `role`, `uri`, an optional `status`, the dependency records, and overlay records. [F] An earlier form used `name_length` in place of `technical_name`, and one example intake also carried a `label`. [F]

### 6.2 The dependency

- A **dependency** is the record an element keeps about one element it relies on. The address of the other element is the dependency. The record holds the purpose for the dependency, the function of the dependency, and a direction. [R: named by the owner on 2026-11-11.]
- The record belongs to the element that has the need. [F]
- The direction is that of the substance, seen from the holder: inbound, outbound or two-way. A request or a receipt is not the direction. [F]
- The structure was first conceived as a hypergraph whose relations are things in their own right and can hold logic. [F] What logic a dependency holds beyond purpose, function and direction is not established. [U]
- The build stores this record under the name `wants`. The rename is decided and not applied. [F]
- **Field names.** The owner chose plain stored names, `why` and `how`, so that agents reading a map need not learn the intake's terms; the intake's concepts were to stay in the procedure, which would say which concept is recorded in which field. [R] That design has not been run: the procedure in the repository removed the concepts. [F] Whether plain names affect intake results is therefore not known. [U]

### 6.3 Overlays (in the map)

- An **overlay** is a named kind of knowledge laid over the map. It was called a layer until 2026-11-11. [R]
- An overlay is defined beneath the internal root. Being defined there is what permits its records to be written at elements, and the definition record is the overlay's schema. [R]
- The number of overlays is not limited, so overlay schemas cannot be delivered in advance. [R]
- An element names the overlays laid on it in `overlays` and the ones masked at it in `masked_overlays`. To remove an overlay's information from one region, mask that region. [R]
- An overlay named at an element applies there and beneath it; a mask stops it from reaching further down; a project-wide list says which overlays are on; one overlay may not be both laid on and masked at the same element. [F: recorded as the owner's decisions of 2026-11-09 under the earlier names. Not built.]
- The build defines one overlay for written specification and has three built-in ones: sources, skills and memory. [F]
- Whether the server checks an overlay record against its definition, so that a new overlay needs no code, was asked and not answered. [U]

### 6.4 The intake procedure

- It infers a map from an artifact. It is the owner's text. [R]
- Its core is its concepts. Some of its terms are coined and slightly open in meaning by design; the meaning settles from the context of use. [R]
- The owner tested it over months, across models and across artifact types. [F]
- A version the owner calls pure defines a shallow operation whose result is a minimal, coarse shape; parts combined away are kept as inactive subtypes to which knowledge may still attach. [F]
- A longer version, which the owner calls canonical, works well and restates the same rules in several ways. [F]
- The procedure in the repository is neither. It is a rewrite that carries markers left by an AI tool, has the tool's commands merged into it, and contains none of the coined concept terms. [F]
- Which text is current, and how it enters the repository, is open. [U]
- Changing a finished map is how new functionality is recorded. The owner says "refining" is not the best word for it. [F] No replacement term is established. [U]

### 6.5 Components in the repository [F]

| Component | Description |
|---|---|
| MCP server | Three implementations of one tool: Rust, Node, Python. |
| Stores | Rust keeps a map in a graph database, with one server process for each home folder. Node and Python keep it in SQLite, one narrow table for each field and each overlay. |
| Conformance suite | Sends the same commands to all three and compares the answers. |
| Host | A Rust program that serves the web interface's files and forwards reads, writes and change events between a page and the server. |
| Web interface | Two pages exist. Neither is accepted (section 7.4). |

**Requirement on storage.** Agents see elements with their fields together. The Node and Python stores hold the data by field, not by element, and manage it properly. [R]

### 6.6 The web interface as a concept

The web interface is the surface through which a person sees the map and moves through it. Section 7 treats it in full.

## 7. Web interface: navigable surface and base requirements

"Base navigable surface" is the term of the task that commissioned this document. It is not yet a term the project evidence defines. [U] This section uses it for the part of the web interface that every use of the interface shares.

### 7.1 Purpose

- The map is the primary work surface. The interface is not a dashboard. [R]
- The interface exists so that a person can explore the project's functional design. The map view is a way to do that, not an end in itself. [R]
- The system is compact, and it needs a proper interface that is legible. [R]

### 7.2 What the owner requires of a new interface

- It is original and written from scratch. It is not a continuation of either existing page, and it is not a recovery of an earlier design. [R]
- It surpasses both existing pages. [R]
- It is legible and dynamic. [R]
- It has a designed system of easing and zooming that is intuitive, smooth and professional. [R]
- Graphics-processor effects such as shaders, refraction and themes built on them are not what was asked for. The owner describes the earlier page that has them as heavy on the processor and bloated. [F]
- The closest existing example of the feel the owner wants is a map viewer in a sibling repository. It is an example, not a base to build on. [F]
- It is improved by repeated iteration on one thing at a time. [R]

### 7.3 Established elements of the base surface

From the owner's two requirement texts and from corrections given in the sessions.

**Identity and position**
- The project's identity, the map's title, breadcrumbs and the zoom level are visible. [R]
- The interface is dark first and designed for the desktop first; narrow screens keep the essential tasks usable. [R]
- Persistent controls are few. A compact menu hides itself and can be brought back by an obvious control. [R]

**Navigation**
- Pan and zoom are smooth and predictable, with zoom in, zoom out and fit to view. [R]
- A single click selects an element and shows its details. [R]
- A double click moves into an element's nested content; breadcrumbs or a back action lead out. [R]
- A control-click moves to the broader context, and a short hint makes that discoverable. [R]
- Every narrowing of the view has a clear way back. The owner reported that one page gave no clear way to back out. [R]
- Elements fold and unfold. An element with hidden content is distinguishable from one without, and its state is shown. [R]
- A person can make an element the new focal point; the interface explains the change and can reverse it. [R]

**Modes**
- Three modes: the map, a focused element with its details, and presentation. Changing mode keeps the project, the path, the focal element and useful view context. [R]

**Projects**
- One web interface serves several registered projects. [R]
- A person can switch projects and follow a link from one project to another, with a clear route back. Project boundaries are explicit. [R]

**Overlays, agents and activity**
- Controls show or hide each overlay, toggle all, and isolate one, with distinct visible, hidden and isolated states. [R] The owner found the wording of such controls on one page meaningless, so the controls must say what they do in the system's own terms. [R]
- Agent presence is shown quietly: who, what state, and where. [R]
- New activity is identifiable and never moves the view or takes focus. [R]

**Content**
- Lines show the direction in which substance moves, and it matches the recorded direction. [R]
- The interface shows purpose, function and direction in plain words. The intake's abbreviations never face a person. [R]
- Unrequested text does not cover the lines. [R]
- Lines with right-angle turns are preferred; the owner found curved lines illegible. [R]
- The owner intends names to float into free space where they can be read. [F] How is not established. [U]
- The map view, a structured view of the specification, and a Markdown document are views of one state. Accepted edits appear in all of them; the exported document matches what is on screen. [R]
- A person can edit the specification; an agent can propose changes; each proposal shows its reason and evidence and can be accepted, rejected or edited first. Unaccepted proposals are never presented as fact. [R]
- Statements are distinguished by evidence: backed by a source, inferred, proposed by an agent, accepted, rejected or unverified. [R]

**Honesty**
- Simulated data and services are labelled. The map model and the event sources are replaceable, so a real service can take the place of a simulated one. [R]
- No control is inert, and no feature is added to give an appearance of completeness. [R]

**Entry**
- The command that starts the interface prints its address, and the server's instructions tell agents to give that address to the person. The address is not a feature shown inside the page. [R]

### 7.4 What exists [F]

- A page at the host's root, written with a component framework. The owner rejected it.
- A page at `/classic/` that is a port of an earlier Metaform page, with a two-dimensional and a three-dimensional map. The owner judges it better than the first page, and states that porting it was not what was asked.
- The host answers a list of projects, forwards a read command, forwards a write command when the request comes from the page's own address, streams change events, and serves the page's files.

### 7.5 What the base must remain independent of

- Whether its data is real or simulated. [R]
- The intake procedure's abbreviations and internal terms. [R]
- Graphics-processor effects. [I: from the owner's description of what was not asked for.]
- Any one project's content. [I: one interface serves several projects.]

### 7.6 Not established [U]

- The page's layout, its routing, its component structure and its technology. The two requirement texts name a component framework; the later requirement is an original design from scratch. Which governs the technology is not settled.
- Whether three modes, dockable panels, proposals and export belong to the base or are added to it.
- The motion system itself: its timings, its rules and its measures. An agent's proposal exists in a separate design document; it is a proposal and not a requirement.
- Acceptance measures for legibility and performance.

## 8. Reuse of the base surface by another project

**What the evidence supports.**

- The owner works on several related projects, and one repository holds two of them. [F]
- One interface is required to serve several registered Metaform projects. [R] That is several maps in one interface. It is not the same as another software project adopting the interface.
- In an earlier Metaform system, separate modules declared tools and panels, and one page placed them. [F] This describes that system. It is not a requirement on the new one.
- The task that commissioned this document treats reuse of the base surface by another project as a distinct concept. [F]

**What is not established.** [U]

- Which project would adopt the base, and for what.
- What is reusable: the motion system, the map view, the frame around it, or all of it.
- What the adopting project supplies: its data, its terms, its views, its server.
- How the base is taken: copied, packaged, or served.
- What the base must not assume about the adopting project.
- Compatibility between versions of the base and its adopters.

**Conservative recommendation.** [I] Until these are decided, keep the base free of Metaform's own terms and data shapes at its edges, so that a later decision is not closed off. Do not build a packaging or integration mechanism.

## 9. Feature overlays within the base surface

**Defined by evidence:** an overlay is a named kind of knowledge laid over the map, which does not change the map and can be masked (section 6.3). [R]

**In the interface, by evidence:** the interface shows overlays and lets a person show, hide and isolate them (section 7.3). [R]

**Not defined by evidence:** a "feature overlay" as something that adds navigation, views or behaviour to the base surface. The task that commissioned this document names it; the project evidence does not define it. [U]

Unresolved for feature overlays within the base: [U]

- whether a feature overlay is the same thing as a map overlay shown in the interface, or a separate concept that shares the word;
- whether it may add or alter navigation, views, behaviour or context;
- how overlays are selected, composed and ordered;
- what happens when two conflict;
- whether one is isolated from another;
- when one starts and ends.

**Stable and extension responsibilities.** [I] By the meaning the owner gave the word for the map, an overlay adds without changing what is beneath it and can be removed cleanly. If feature overlays follow the same meaning, the base keeps navigation, identity and the way back, and an overlay adds to them and never replaces them. This is an inference from the word and binds nothing.

## 10. MCP server

**Role.** The server is how agents read and write a project's map. [F]

**Established.**

- It offers one tool. [R]
- The intake procedure is to be handled by the server. [R]
- The server's instructions tell an agent to give the person the web interface's address when it finishes an intake or changes the map. [R]

**As built.** [F]

- At connection it sends that one instruction. It lists one tool and one resource, which is the connection's map. It lists no prompts.
- It does not deliver the intake procedure. An agent has the procedure only when a person or another agent supplies it.
- In the Rust implementation one server process owns each home folder, and each agent's connection is a small forwarding process.
- It announces changes, which the host passes to an open page.

**Unresolved.** [U] The form in which the server delivers the intake procedure. An agent has proposed an operation that returns it; that is a proposal.

Nothing here should be read as a statement about MCP in general.

## 11. Tooling model and progressive discovery

### 11.1 The tool

One tool. Its input is one object with one key. The key is an operation or an address. [F] The design is the owner's: the stored form of the map is nested data, and a command is that same form under one key. [R]

| Operation | Responsibility | Status |
|---|---|---|
| add, update, delete | Write. An element is written in the form it is stored in. | [F] |
| a bare address | Read one element. | [F] |
| a key that starts with a period | Return the stored form beneath that path. | [F] |
| orphaned | List elements nothing relies on. | [F] |
| map | Return the shape alone. | [F] |
| goto | Place the agent at an address and return what is linked there; a later visit in the same context returns only what changed. | [F] |
| help | With nothing: the form of help, which names what can be asked. With a name: the form of that one thing, with pointers to what can be asked next. One level for each answer. | [R] as to purpose; [F] as built |

### 11.2 Progressive discovery

**Rule.** No information is presented before it is needed, and nothing is presented that is not needed. [R]

**Intended flow.** [F]

1. On connection an agent receives the tool's name, a short description and the list of operations: 672 bytes in the build.
2. An agent that wants a command's shape asks help, one level at a time.
3. An agent that sends a wrong command receives the reason and the command that would be accepted.
4. An overlay's schema is read from the overlay's definition in the map when the agent goes to write that overlay.

**Rationale.** [F] The tool's whole definition is placed in front of a model before its first call. Earlier, that definition was about twelve kilobytes and restated one simple shape for every operation. An agent that never wrote still received all of it. The correction mechanism already teaches each shape at the moment of need, so the long definition repeated it at a cost.

**Boundaries.** [R] Validation concerns the shape and integrity of a command. It never judges what an intake inferred. An agent added a rule that refused a purpose for its wording; the owner rejected it, and it was removed.

**Known departures in the build.** [F] Two refusals hand back no usable command. Some answers hold items an agent did not need, such as counts of zero.

## 12. Task-relevant context and information boundaries

- **Relevance is positional.** Knowledge attaches to the element it concerns. An agent placed at an element receives what is linked there. [F]
- **Delivered once.** What an agent has already received in a context is not sent again; a repeated visit names what is unchanged. After a reset the agent can read it again. [F]
- **Overlays scope knowledge.** Where an overlay is laid on and where it is masked decide where its knowledge applies. This is designed and not built. [F]
- **The shape first, detail on request.** The whole-map read gives addresses and dependencies with no detail. [F]

**Reducing irrelevant context is not the same as withholding needed information.** [R] The rule removes what an agent does not need yet. It does not remove what an agent needs to act correctly:

- A command that would break the map is refused, with the correction. That is never omitted.
- The shape of any command can always be asked for.
- A delete that would leave a dependency pointing at nothing is refused, with the command that removes the dependency first.

**Unresolved.** [U] How relevance is decided for an agent that is not placed at an element. How the intake procedure is selected for delivery when several prompts or modes exist. Whether empty counts and built-in overlay pointers in the placed read are the owner's design or tooling to trim.

## 13. End-to-end workflow

This workflow is illustrative. It shows how the parts relate. It prescribes nothing beyond what the earlier sections establish.

1. A person starts the web interface. The command prints an address.
2. An agent connects to the server and receives the short tool definition.
3. The agent asks for the shape of the map and sees what the project is.
4. The agent goes to the element its task concerns and receives what is linked there.
5. To record something, the agent asks help for the operation it needs, or sends its best attempt. A wrong attempt returns the correct command, which it sends.
6. To write an overlay record, the agent reads that overlay's definition first.
7. The server announces the change. The open page marks the changed element and does not move the view.
8. The person selects the element and reads its purpose, function and direction in plain words; moves into it; and comes back by the way that is always shown.
9. The agent tells the person the interface's address.

For work scoped to part of a project, an overlay is laid on the elements the work concerns and removed when the work is done. The map is the same before and after.

## 14. Updating and maintaining the project understanding

**Established.** [R]

- Settled matters are written into the project's specification. A question is recorded as open and never as a decision.
- A statement is not decided until the owner decides it. An agent's recommendation is not a decision.
- The owner's intent is recorded in the writer's words with its reason, not by quotation.
- The intake procedure, the schema and the tool contract are changed only on the owner's direct instruction. The owner has stated that tooling may be made more efficient; the semantics may not be changed.
- Preserved source material in the repository is read and not edited. The owner's own folder is not edited.

**Procedure.** [I]

1. State what changed and who decided it.
2. Find every statement and component the change touches, including this document's glossary and section 17.
3. Compare the change with the principles in section 5. Report any conflict to the owner before applying it.
4. Apply a rename in one pass across tooling, and report each place it could not be applied.
5. Keep what is unresolved visible in section 18. Do not remove a question because work has moved on.
6. Record what the change did not cover.

## 15. Building from and evaluating work against this specification

### 15.1 Building

- Work on the semantics is the owner's. Work on tooling fits the semantics. [R]
- A change is committed after a test in which it works, and the commit says what was tested and what it showed. [R]
- A claim of completion matches its evidence: proposed, attempted, completed and verified are different states. [R]
- The three implementations are kept in agreement by the shared suite. [F]

### 15.2 Evaluation method [I]

For a proposed piece of work:

1. State what it changes.
2. List the requirements [R] it touches.
3. For each, find evidence that the work satisfies or breaks it.
4. Classify: **compliant** when every touched requirement is satisfied; **non-compliant** when any is broken; **indeterminate** when the outcome depends on something marked [U].
5. Do not count an interpretation [I] as a requirement. Report it apart.

### 15.3 The method applied

| Proposed work | Finding | Basis |
|---|---|---|
| Port an earlier page as the interface | Non-compliant | The interface is to be original and from scratch (7.2). |
| Show the interface's address inside the page with a copy control | Non-compliant | The address is printed by the command and told by agents; no feature for appearance (7.3). |
| Add a check that refuses a purpose for its wording | Non-compliant | Never gated or judged (5.4, 11.2). |
| Tell intake agents to record more elements | Non-compliant | Shallow and coarse; the procedure is not altered (5.1, 5.5). |
| Publish the list of operations in place of the full schema | Compliant | Small surface, progressive discovery (5.6, 5.7). |
| Add help that returns one level for each answer | Compliant | Progressive discovery (11.2). |
| Rename the stored dependency record | Compliant in tooling; indeterminate in the procedure | The name is decided; which procedure text receives it is not (18). |
| Make the base surface a package for another project | Indeterminate | Reuse is not defined (8). |
| Let a feature overlay add a view to the base | Indeterminate | Feature overlays are not defined (9). |
| Define a new map overlay at a two-segment address beneath the internal root | Indeterminate | The form of an overlay's address is not settled (18). |

## 16. Canonical terminology and glossary

**Settled terms.**

| Term | Meaning | Not to be confused with |
|---|---|---|
| Metaform | The project, and a map made by it. | |
| Element | A functional part, named as a type. | A file, function or class. |
| Address | The dotted name of an element. | A file path. |
| Dependency | The record an element keeps about an element it relies on. Decided 2026-11-11. | An imported package. A dependency here can exist in a photograph or a story. |
| Overlay | A named kind of knowledge laid over the map. Decided 2026-11-11. | A visual layer in a drawing. |
| Mask | A stop that keeps an overlay from applying at an element and beneath it. | Deletion. A mask hides. |
| Progressive discovery | The rule of section 11.2. | Lazy loading in general. |
| Operative Purpose | What a receiving element seeks to accomplish through a providing element. | The purpose of the whole project. |
| Encounter Function | What the providing element does in that meeting that satisfies the purpose. Open in meaning by design. | The element's function in general. |

**Competing terms. None is silently resolved here.**

| Concept | Forms in the evidence | State |
|---|---|---|
| The dependency record | join; purpose record; wants; dependency | Dependency is decided. The build still stores `wants`. |
| Knowledge over the map | layer; knowledge layer; composed element layer; overlay | Overlay is decided. The build still says layer. |
| The two arrays on an element | `layers` and `blocked_layers`; `overlays` and `masked_overlays` | The second pair is decided, not applied. |
| The purpose and function fields | `op` and `ef`; goal and function; `why` and `how` | `why` and `how` are the owner's choice for stored names. Not yet run as designed. [U] |
| The direction field | an information flow direction with send, receive, both; intent; `direction` with inbound, outbound, two-way | The last is in the build. |
| Roles | DE, SE, NE and an outside party; Definitive, Supportive, Notable, Divergent | The four words are in the build. |
| The S role | Substantial Element; Supportive Element | Two expansions in two procedure texts. [U] |
| The outside party | named by a legal term for a beneficiary in the procedure texts; "downstream party" on pages | Whether it has a role is open. [U] |
| The name read from the address | `name_length` (a count); `technical_name` (the words) | The second is in the build. |
| The intake procedure's title | Two different titles in two texts | [U] |
| The project's writing standard | One acronym with two expansions in two documents | [U] |
| Adding functionality to a finished map | refine | The owner says it is not the best word. No replacement. [U] |
| Base navigable surface; feature overlay | Terms of the commissioning task | Not defined by project evidence. [U] |

Spelling as used in the build: `technical_name`, `masked_overlays`, `project-map` for the tool, `un_built` for the status of unbuilt functionality.

## 17. Requirements and behavioral expectations

Each line is an established requirement unless marked otherwise.

**Semantics**
1. Do not alter the intake procedure's concepts, terms, definitions or examples.
2. Do not add rules on top of the procedure.
3. Hold the procedure in the repository as the owner wrote it.
4. Do not gate or judge an intake. Do not grade a map.
5. Keep the map shallow and coarse.

**Tool and server**
6. One tool, with a list of operations, well under one kilobyte.
7. Present no information before it is needed and none that is not needed.
8. Answer a wrong command with the reason and the command that would be accepted.
9. Provide help that shows how to ask for the form of any other operation.
10. The server handles the intake procedure. [Form unresolved.]
11. The server's instructions tell agents to give the person the interface's address.
12. An overlay is defined beneath the internal root; its definition is its schema.

**Implementations**
13. Rust, Node and Python serve the same purpose under one requirement.
14. Rust takes a more modern approach than the other two.
15. Node and Python present elements with fields together to agents and store by field.

**Web interface**
16. Original, from scratch, surpassing both existing pages.
17. Legible and dynamic, with a designed system of easing and zooming.
18. The map is the primary surface.
19. A clear way back from every narrowing of the view.
20. The view does not move when the map changes.
21. Direction on screen matches the recorded direction.
22. Plain words for a person; no intake abbreviations.
23. No inert control and no feature for appearance.
24. Simulated behaviour is labelled.
25. One interface serves several registered projects.
26. The map view, the structured view and the Markdown document show one state.

**Working practice**
27. Record settled matters; keep questions open.
28. Interpret the owner with the reason; do not quote.
29. Match every claim of status to its evidence.
30. Improve by changing one thing at a time and measuring the same things each time.

## 18. Open questions, ambiguities, and decisions needed

**Semantics**
1. Which text is the current intake procedure, and how does it enter the repository? Until this is answered, no intake run in this repository is evidence about the owner's procedure.
2. Do plain stored names for purpose and function hold when the procedure keeps its concepts? One run each way on the same artifact and model would answer it.
3. What does a dependency hold beyond purpose, function and direction? An early procedure's record also held a relation, an observation and the parts combined away.
4. Does an outside party have a role?
5. Is collection a root?
6. What is the word for adding functionality to a finished map?

**Overlays**
7. Is the internal root named for the overlay, and may an overlay's address have more than one segment beneath it?
8. Does the server check an overlay record against the overlay's definition?
9. What is the word for naming an overlay at an element?

**Server and tool**
10. In what form does the server deliver the intake procedure?
11. Which parts of the placed read and the shape read are the owner's design, and which may be trimmed?
12. What does "a more modern approach" require of the Rust implementation beyond what it does now?

**Web interface**
13. What technology is the new interface written in?
14. What are the rules and measures of the easing and zooming system?
15. What belongs to the base surface, and what is added to it?
16. What does reuse by another project mean: which project, what is reused, what the adopter supplies, and how it is taken?
17. What is a feature overlay within the base surface, and is it the same concept as a map overlay?
18. For feature overlays: selection, composition, precedence, conflicts, isolation and lifecycle.

**Scope**
19. How does this repository relate to the scoring and mutation pipeline and to the wider architecture named in section 3?
