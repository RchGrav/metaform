# Metaform: project specification and agent guide

## 1. Title and specification status

**Document:** Metaform project specification and agent guide.
**Date:** 2026-11-11. **Status:** Draft for the founder's correction. It is not definitive: section 18 lists material questions that are open.

**Evidence base.** The founder's statements in working sessions from 2026-10-30 to 2026-11-11, 1,089 messages read in full; the founder's documents (an intake procedure, a mutation framework, a semantic compilation guide, a judge module contract, a one-page query design, two interface requirement texts, an architecture note for the wider system); and the state of the repository on 2026-11-11.

**Status marks.** Each consequential statement carries one mark.

| Mark | Meaning |
|---|---|
| **[R]** | Established requirement: the founder required it. |
| **[F]** | Established fact or description: stated or consistently observed, not necessarily required. |
| **[I]** | Conservative interpretation: a cautious inference or a recommended practice. It binds no one. |
| **[U]** | Unknown or unresolved: not established, in conflict, or waiting for a decision. |

**Dates.** Where the founder decided a matter more than once, the latest statement governs, and this document gives its date. Within one day the record does not show which message came first.

**Limits.** The founder corrected the agents' reading of this project several times during the sessions this document draws on. Statements marked [I] are the most likely to be wrong. The founder's own wording governs wherever it differs from this document.

## 2. Executive summary

Metaform keeps a small map of what a project does, so that an agent can orient itself without spending its limited reasoning on working out what the project is. [F]

- The map is a set of elements at dotted addresses. Each element records what it relies on, for what purpose, and how the other element serves that purpose. [F]
- The map describes functionality, not files or code. It is an inference, and it is never graded. [R]
- Knowledge about the project attaches to elements as overlays: named kinds of records laid over the map without changing it. [R]
- Agents reach the map through one tool on a Model Context Protocol (MCP) server. The tool's definition is to stay well under one kilobyte and holds a list of operations. [R]
- Every answer follows progressive discovery: nothing is delivered before it is needed, and nothing that is not needed. [R]
- A wrong command is answered with the reason and the command that would be accepted. That correction is how an agent learns a command's shape. [R]
- The tool exists in Rust, Node and Python. The three serve the same purpose under one requirement. The Rust version is to take a more modern approach than the other two. [R]
- A web interface lets a person see and move through the map. The founder requires an original interface, written from scratch, that is legible and dynamic, with a designed system of easing and zooming. No interface that meets this exists yet. [R] [F]

The largest unresolved matters are: the two points of the intake procedure's gap fill that need the founder (section 18); the technology and the motion rules of the new web interface; and what reuse of the interface by another project requires. [U]

## 3. Purpose, scope, and intended use

**Purpose of this document.** To give a technically capable reader, or an agent, enough to understand Metaform, to work on it without altering what must not be altered, and to judge proposed work against what the founder has established.

**In scope:** the map and its terms; the MCP server and its one tool; progressive discovery and task-relevant context; overlays; the three implementations; the web interface.

**Out of scope, named for context only:**

- A pipeline that uses a map to score an artifact from each consumer's side and to change it under rules (stages named intake, score, mutation instruction, weight decay and export, with an optional judge stage). [F] The intake gives the understanding that a mutation needs: a thing must be fully understood before it is changed, and that understanding is what protects it from becoming a different thing. [F] The interface between that pipeline and this repository is not specified. [U]
- A wider system of which Metaform is the context engine. [F] Metaform is universal and is its own project; Topogee is a project built with it. [R] The MCP server can work alone, and it works together with the wider system's core when both are present. [R]
- An agents module, specified after the MCP server, that owns agent names and messaging. [F]
- Tickets. A ticket holds knowledge that does not last; the map holds knowledge that does. A ticket has a home element, and taking a ticket orients an agent as `goto` does. [F] The ticket mechanism is not a base mechanism of Metaform. [R]
- A separate multi-agent discussion tool kept in the same repository. [F]

**Intended users.** People who want to see what a project is and to direct work on it; agents that need to orient in a project and record what they learn. [F]

## 4. Project intent and intake method

### 4.1 Intent

- The cost Metaform saves is a reasoning cost. An agent has a limited capacity for tracking and understanding. Orientation in a project draws on that capacity. Metaform does the orientation once and keeps the result. [F]
- Metaform does not raise a model's ability. It preserves the capacity that lets the model perform well. [F]
- The saving is not measured in tokens or money. A document that claims otherwise misstates the project. [R]
- The map answers one question at a glance: what is this project. [F]
- The map is also the footing for further uses the founder plans, across artifact types that include software, photographs, stories and scripts. Those uses are not specified here. [F] [U]

### 4.2 Two different things are called intake

1. **The intake procedure** is a project concept: the procedure by which an agent infers a map from an artifact (section 6.4).
2. **The intake method of this section** is guidance for an agent that must take in information about the Metaform project itself, to maintain this specification or to prepare work.

### 4.3 Intake method for project information [I, except where marked]

1. **Find the current source before reading any.** Several versions of most documents exist, including rewrites made by agents. Ask the founder which text is current. Do not assume the copy in the repository is. [R: the founder stated that the repository's procedure is an old one and not the current one.]
2. **Read whole documents.** Headings and summaries have misled agents on this project. [F]
3. **Extract, for each source:** goals; scope; requirements; constraints; actors; components and how they relate; terms with their exact spelling; details of the web surface; what is said about reuse and extension; rules for selecting context; overlays; open questions.
4. **Mark each extracted statement** with one of the four statuses in section 1.
5. **Record the reason with the rule.** The founder asks to be interpreted correctly, with the reason, and not to be quoted. A rule without its reason has been misapplied more than once. [R]
6. **Separate the founder's semantics from tooling.** The intake procedure's concepts, coined terms, definitions and examples are the founder's semantics. The server, schema, commands, stores and pages are tooling. [R]
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
9. **One purpose, three implementations.** Rust, Node and Python serve the same purpose under one requirement; Rust takes the more modern approach, which is its graph database. [R]
10. **Honest labelling.** Simulated behaviour is labelled as simulated. Unbuilt behaviour is not described as working. [R]
11. **Plain technical English** for project prose, with the project's own terms and no invented ones. [R]
12. **Own code.** No new dependencies and no copies of outside libraries in the repository; outside code may be read for ideas and then written anew. [R]
13. **No logic without an observed failure.** A check, a gate or a step is added only to fix a failure that was observed. [R]
14. **No ceremony in the tool.** The tool has no start and no stop for an intake, and will not have one. Data lives in one place and is shown. Ceremony, where it is wanted, belongs in a prompt. [R]
15. **The map grows.** A functionality that changes is a different functionality and a new element. Work on an artifact may mutate it and may not transform it into a different thing. [R]
16. **Built for other projects.** Metaform is not designed around managing itself. [R]

## 6. Concepts and architecture, including the web interface

### 6.1 The map

- An **element** is a functional part of an artifact, named as a type. [F]
- An **address** is a dotted path from general to specific. Read in reverse it is the element's ordinary name. Each prefix is itself a complete type. A segment never names a language, an encoding, a genre or a particular product. [R]
- **Roots.** Four roots hold what is inside the artifact: code, document, media, data. These four are always local to the project they are used in. Two more hold what is outside it: upstream, for what it relies on, and downstream, for the elements or entities that rely on it. An upstream address continues with one of the four base types, as in `upstream.code.engine.game`, and can refer to the outside project that meets the requirement. [R: 2026-11-11] One further root is internal: it is a schema and an input validation, it holds overlay definitions, and the intake procedure does not use it. [R] The repository's code also accepts a root named `collection`. The founder's six roots do not include it, so the build departs from the design here. [F]
- **Roles.** Each element inside the artifact has one of four roles: Definitive, Supportive, Notable, Divergent. One element is Definitive. [F] Earlier texts name the roles by the abbreviations DE, SE and NE. SE is Supportive. It was Substantial until 2026-11-03; the founder changed it because substantial and notable were too alike, and because supportive states that the element is coupled without an extra field. [R]
- **Outside parties.** A party outside the artifact has no role. The intake's term for such a party is for inference only: it does not appear in an address or in front of a person. The address names the type of party. [R] The term is kept in the procedure because its definition makes the agent reason past the developer and the user. Asking who the project is for does not give a useful answer. [R: 2026-11-11]
- **Element fields in the build:** `technical_name`, `name`, `role`, `uri`, an optional `status`, the dependency records, and overlay records. [F] An earlier form used `name_length` in place of `technical_name`, and one example intake also carried a `label`. [F] `technical_name` replaced `name_length` because a count does not give the name; `technical_name` is checked against the last words of the address read in reverse, and `name` is the ordinary name. [R]
- **Stored and shown keys.** The store keeps keys in lower camel case. An agent sees snake case. [R]
- **Dictionaries.** Anything keyed by a unique name is a dictionary and not an array. An answer to a query is a bare array. [R]

### 6.2 The dependency

- A **dependency** is the record an element keeps about one element it relies on. The address of the other element is the dependency. The record holds the purpose for the dependency, the function of the dependency, and a direction. [R: named by the founder on 2026-11-11.]
- The record belongs to the element that has the need. [F]
- The direction is that of the substance, seen from the holder: inbound, outbound or two-way. A request or a receipt is not the direction. [F]
- The understanding of a type is a relation of three parts: the purpose of the element that receives, the function of the element that provides, and the functionality itself. An element with no dependency of its own is still relied on by something, or it would not be a type. [F]
- The dependency record is itself an overlay. It sits in a reserved group named for the intake, so it does not appear in the list of overlays and cannot be deleted. [R: 2026-11-03]
- The structure was first conceived as a hypergraph whose relations are things in their own right and can hold logic. [F] What logic a dependency holds beyond purpose, function and direction is not established. [U]
- The build stores this record under the name `wants`. The rename is decided and not applied. [F]
- **Field names.** On 2026-11-07 the founder chose plain stored names, `why` and `how`, as more universal, so that agents reading a map need not learn the intake's terms; the intake's concepts were to stay in the procedure, which would say which concept is recorded in which field. [R] That design has not been run: the procedure in the repository removed the concepts. [F] Whether plain names affect intake results is therefore not known. [U]

### 6.3 Overlays (in the map)

- An **overlay** is a named kind of knowledge laid over the map. It was called a layer until 2026-11-11. [R]
- An overlay is defined beneath the internal root. Being defined there is what permits its records to be written at elements, and the definition record is the overlay's schema. [R]
- The definition is the complete input validation for the overlay's records. For each field it holds a sentence and the grammar rules of that field, and it holds one sentence that must read correctly when the fields are placed in it. [R]
- An overlay's address may have several segments beneath the internal root, and a root type may follow the internal root. A programming language is a medium and not a functionality, so it has no element in the map and is an overlay. [R]
- After the intake, overlays are free to add. An overlay may hold the insights for one piece of work and be removed when that work ends. [R]
- The number of overlays is not limited, so overlay schemas cannot be delivered in advance. [R]
- An element names the overlays laid on it in `overlays` and the ones masked at it in `masked_overlays`. To remove an overlay's information from one region, mask that region. [R]
- An overlay is linked at the element where it is needed. Defining an overlay does not turn it on: it is on when the core database, which tracks projects, lists it as enabled. An enabled overlay applies at the element it is linked to and at everything beneath that element, toward the leaves and never backward. A mask stops it from reaching further down. One overlay may not be both linked and masked at the same element. [R: 2026-11-09 and 2026-11-10, under the earlier names. Not built.]
- The build defines one overlay for written specification and has three built-in ones: sources, skills and memory. [F]
- An inbox for messages to an agent is to be an overlay kept in its own file. It comes after the base intake system. [F]
- How the sources overlay fits this scheme is not stated in the record. [U]

### 6.4 The intake procedure

- It infers a map from an artifact. It is the founder's text. [R]
- Its core is its concepts. Some of its terms are coined and slightly open in meaning by design; the meaning settles from the context of use. [R]
- The founder tested it over months, across models and across artifact types. [F]
- A version the founder calls pure defines a shallow operation whose result is a minimal, coarse shape; parts combined away are kept as inactive subtypes to which knowledge may still attach. [F]
- A longer version, which the founder calls canonical, works well and restates the same rules in several ways. [F]
- The procedure in the repository is neither. It is a rewrite that carries markers left by an AI tool, has the tool's commands merged into it, and contains none of the coined concept terms. [F]
- **The base text, decided 2026-11-11.** The founder's pure text is the base. Its gap is the two outside roots: it defines the four base types and nothing for what is outside the project. The gap fill adds upstream and downstream. [R]
- The pure text is in the repository unaltered at `metaform/intake/pure_intake.xml`. A proposed gap fill is beside it at `metaform/intake/intake.proposed.xml`. It adds lines and alters none. The founder has not accepted it. The procedure that agents are given today is still the rewrite. [F]
- One agent performs an intake. Several agents work at once only when they are orchestrated for other work. [R]
- The procedure is delivered as the instructions of the intake agent (2026-11-07; before that it was a skill). On 2026-11-11 the founder said the intake is to be handled by the MCP server. The form of that is open (section 10). [F] [U]
- The intake's terms are for the agent that expands the map. Agents that read a map are not taught them. [R]
- After the intake the map grows: new functionality is a new element. The founder says "refining" is not the best word for this and has not chosen another. This document says "growing the map". [I]

### 6.5 Components in the repository [F]

| Component | Description |
|---|---|
| MCP server | Three implementations of one tool: Rust, Node, Python. |
| Stores | Rust keeps a map in a graph database, with one server process for each home folder. Node and Python keep it in SQLite, one narrow table for each field and each overlay. |
| Conformance suite | Sends the same commands to all three and compares the answers. |
| Host | A Rust program that serves the web interface's files and forwards reads, writes and change events between a page and the server. |
| Web interface | Two pages exist. Neither is accepted (section 7.4). |

**Requirements on storage.**

- Agents see elements with their fields together. All three stores hold the data by field, not by element, and manage it properly. Convenience for the agent and performance in the store are both required. [R: 2026-11-09]
- The graph database of the Rust implementation is the modern approach the founder means. He describes it as the state of the art and useful for certain projects, and the other two as fine. [R]
- Writes go through a queue with fair queuing. The graph database needs a data engine in Rust that queues several writers. [R]
- One core database lists the projects. Each project has its own database, with the same file name in every project, in a folder named from the project's path. Only the databases in use are open. [R: 2026-11-02]
- The home folder is `~/.metaform`. Settings and the registry of projects may be JSON. [R]
- The Node version was first made quickly and without concurrency. It must not become the design. [R]

### 6.6 The web interface as a concept

The web interface is the surface through which a person sees the map and moves through it. Section 7 treats it in full.

## 7. Web interface: navigable surface and base requirements

"Base navigable surface" is the term of the task that commissioned this document. It is not yet a term the project evidence defines. [U] This section uses it for the part of the web interface that every use of the interface shares.

### 7.1 Purpose

- The map is the primary work surface. The interface is not a dashboard. [R]
- The interface exists so that a person can explore the project's functional design. The map view is a way to do that, not an end in itself. [R]
- The system is compact, and it needs a proper interface that is legible. [R]

### 7.2 What the founder requires of a new interface

- It is original and written from scratch. It is not a continuation of either existing page, and it is not a recovery of an earlier design. [R]
- It surpasses both existing pages. [R]
- It is legible and dynamic. [R]
- It has a designed system of easing and zooming that is intuitive, smooth and professional. [R]
- Graphics-processor effects such as shaders, refraction and themes built on them are not what was asked for. The founder describes the earlier page that has them as heavy on the processor and bloated. [F]
- The closest existing example of the feel the founder wants is a map viewer in a sibling repository. It is an example, not a base to build on. [F]
- It is improved by repeated iteration on one thing at a time. [R]
- The founder's earlier interface text names React and TypeScript, with a Rust host, and asks that the Rust version be the premium experience. The later instruction, an original design from scratch, governs the design. Whether it also replaces that choice of technology is open (7.6). [F] [U]

### 7.3 Established elements of the base surface

From the founder's two requirement texts and from corrections given in the sessions.

**Identity and position**
- The project's identity, the map's title, breadcrumbs and the zoom level are visible. [R]
- The interface is dark first and designed for the desktop first; narrow screens keep the essential tasks usable. [R]
- Persistent controls are few. A compact menu hides itself and can be brought back by an obvious control. [R]

**Navigation**
- Pan and zoom are smooth and predictable, with zoom in, zoom out and fit to view. [R]
- A single click selects an element and shows its details. [R]
- A double click moves into an element's nested content; breadcrumbs or a back action lead out. [R]
- A control-click moves to the broader context, and a short hint makes that discoverable. [R]
- Every narrowing of the view has a clear way back. The founder reported that one page gave no clear way to back out. [R]
- Elements fold and unfold. An element with hidden content is distinguishable from one without, and its state is shown. [R]
- A person can make an element the new focal point; the interface explains the change and can reverse it. [R]

**Live state**
- The map on screen follows the state of the database continually. A reload is never needed. Changes arrive because commands are applied, not because the page asks at intervals. [R]
- The interface stays responsive while an intake writes. [R]

**Direct navigation by the founder's description of 2026-11-02**
- A click on a box zooms to that box and its direct connections. [R]
- Elements are drawn as nested boxes; the founder liked that form. [F]
- The layout is automatic, in the manner of a flowchart layout, from an engine the project writes itself. [R]
- Keys change the view: one key shows one feature at a time, one zooms through the levels, one starts a tour, and `?` opens the list of keys. [R]
- The tour goes feature by feature and then one functionality at a time. It hides the side panel and annotates the zoomed view. [R]
- A person can send a message to an agent through the interface. [F: stated 2026-11-03; it depends on the agents module, which is not built.]

**Modes**
- Three modes: the map, a focused element with its details, and presentation. Changing mode keeps the project, the path, the focal element and useful view context. [R]

**Projects**
- One web interface serves several registered projects. [R]
- A person can switch projects and follow a link from one project to another, with a clear route back. Project boundaries are explicit. [R]

**Overlays, agents and activity**
- Controls show or hide each overlay, toggle all, and isolate one, with distinct visible, hidden and isolated states. [R] The founder found the wording of such controls on one page meaningless, so the controls must say what they do in the system's own terms. [R]
- Agent presence is shown quietly: who, what state, and where. [R]
- New activity is identifiable and never moves the view or takes focus. [R]

**Content**
- Lines show the direction in which substance moves, and it matches the recorded direction. [R]
- The interface shows purpose, function and direction in plain words. The intake's abbreviations never face a person. [R]
- Unrequested text does not cover the lines. [R]
- Lines with right-angle turns are preferred; the founder found curved lines illegible. [R]
- The founder intends names to float into free space where they can be read. [F] How is not established. [U]
- The map view, a structured view of the specification, and a Markdown document are views of one state. Accepted edits appear in all of them; the exported document matches what is on screen. [R]
- A person can edit the specification; an agent can propose changes; each proposal shows its reason and evidence and can be accepted, rejected or edited first. Unaccepted proposals are never presented as fact. [R]
- Statements are distinguished by evidence: backed by a source, inferred, proposed by an agent, accepted, rejected or unverified. [R]

**Honesty**
- Simulated data and services are labelled. The map model and the event sources are replaceable, so a real service can take the place of a simulated one. [R]
- No control is inert, and no feature is added to give an appearance of completeness. [R]

**Entry**
- The command that starts the interface prints its address, and the server's instructions tell agents to give that address to the person. The address is not a feature shown inside the page. [R]

### 7.4 What exists [F]

- A page at the host's root, written with a component framework. The founder rejected it.
- A page at `/classic/` that is a port of an earlier Metaform page, with a two-dimensional and a three-dimensional map. The founder judges it better than the first page, and states that porting it was not what was asked.
- The host answers a list of projects, forwards a read command, forwards a write command when the request comes from the page's own address, streams change events, and serves the page's files.

### 7.5 What the base must remain independent of

- Whether its data is real or simulated. [R]
- The intake procedure's abbreviations and internal terms. [R]
- Graphics-processor effects. [I: from the founder's description of what was not asked for.]
- Any one project's content. [I: one interface serves several projects.]

### 7.6 Not established [U]

- The page's technology. The earlier text names a component framework; the later instruction is an original design from scratch, and the project's rule is its own code with no new dependencies. [I] Recommendation: plain TypeScript with no framework, drawing to SVG or canvas, with the project's own layout and motion code. The founder decides.
- The page's layout and structure.
- Whether three modes, dockable panels, proposals and export belong to the base or are added to it.
- The motion system itself: its timings, its rules and its measures. An agent's proposal exists in a separate design document; it is a proposal and not a requirement.
- Acceptance measures for legibility and performance.

## 8. Reuse of the base surface by another project

**What the evidence supports.**

- The founder works on several related projects, and one repository holds two of them. [F]
- One interface is required to serve several registered Metaform projects. [R] That is several maps in one interface. It is not the same as another software project adopting the interface.
- In an earlier Metaform system, separate modules declared tools and panels, and one page placed them. [F] This describes that system. It is not a requirement on the new one.
- The task that commissioned this document treats reuse of the base surface by another project as a distinct concept. [F]
- Metaform is universal, and projects other than Metaform are the point of it. Topogee is a project built with Metaform. Agents may make and own a map of their own. [R]
- The record holds no statement that the interface, or a base part of it, is taken into another software project. [F]

**What is not established.** [U]

- Which project would adopt the base, and for what.
- What is reusable: the motion system, the map view, the frame around it, or all of it.
- What the adopting project supplies: its data, its terms, its views, its server.
- How the base is taken: copied, packaged, or served.
- What the base must not assume about the adopting project.
- Compatibility between versions of the base and its adopters.

**Conservative recommendation.** [I] Until these are decided, keep the base free of Metaform's own terms and data shapes at its edges, so that a later decision is not closed off. Do not build a packaging or integration mechanism.

## 9. Feature overlays within the base surface

**Defined by evidence.**

- An overlay is a named kind of knowledge laid over the map. It does not change the map and can be masked (section 6.3). [R]
- A feature overlay is one such overlay: it tags the elements that make up each feature of the project. [R: 2026-11-02] The repository's commit rule names features by this overlay. [F]
- The interface uses the feature overlay to navigate. One key shows one feature at a time. The tour goes feature by feature, then one functionality at a time (section 7.3). [R]
- The interface shows every overlay and lets a person show, hide and isolate each (section 7.3). [R]

**Reading.** [I] The commissioning task's phrase "feature overlays within the base" is read here as this: the base surface is the map and its navigation, and an overlay, the feature overlay first, selects what the base shows and in what order. An overlay adds a way to look at the map. It does not add a panel or replace navigation.

**Rules that follow from the map's overlay rules.** [I]

- Selection: an overlay is available in the interface when it is enabled for the project and not masked at the element in view.
- Isolation: isolating an overlay shows the elements it is linked to and dims the rest. The map beneath is the same.
- Lifecycle: an overlay removed from the map leaves the interface with no trace.
- Two overlays do not conflict, because neither changes the map.

**Not established.** [U] Whether an overlay may bring its own view or controls into the interface. The order in which a tour visits features. What the interface shows when two isolated overlays share no element.

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

- The tool is for reading and writing data. Commands of the command line, such as export, stay out of it. A tool operation may be used through the command line; the reverse does not hold. [R]
- The server keeps no intake session: no start, no stop, no lock (section 5, principle 14). [R]

**Unresolved.** [U] The form in which the server handles the intake procedure. The record has the procedure as the intake agent's instructions (2026-11-07) and the founder's later statement that the server handles intake (2026-11-11). An agent's earlier proposal of an intake operation is withdrawn: nothing may act as a start. [I] Recommendation: the server offers the procedure as an MCP prompt, which a person or an orchestrating agent selects, and which costs nothing until selected.

Nothing here should be read as a statement about MCP in general.

## 11. Tooling model and progressive discovery

### 11.1 The tool

One tool. Its input is one object with one key. The key is an operation or an address. [F] The design is the founder's: the stored form of the map is nested data, and a command is that same form under one key. [R]

| Operation | Responsibility | Status |
|---|---|---|
| add, update, delete | Write. An element is written in the form it is stored in. | [F] |
| a bare address | Read one element: its own content, without the full account of what relies on it. | [R] |
| a key that starts with a period | Return the stored form beneath that path. A key with no period is a command. | [R: 2026-11-09] |
| orphaned | List elements nothing relies on. | [F] |
| map | Return the shape alone. | [F] |
| goto | Place the agent at an address. Return who relies on the address, what it relies on, the overlays linked there, the front matter of each skill there (not the skills), and counts of records such as memories (not the records). The server notes where the agent is. A later visit in the same context returns only what changed. | [R] as to content; [F] as built |
| search | Match anything in the map, and answer with the address where it was found and the overlay it was found in. | [R: 2026-11-03]. Not in the build. |
| memory | Read and write the memories of the element where the agent is. Presence at the address is the only way to reach them. | [R: 2026-11-03]. The build keeps memory as an overlay. |
| help | With nothing: the form of help, which names what can be asked. With a name: the form of that one thing, with pointers to what can be asked next. One level for each answer. | [R] as to purpose; [F] as built |

### 11.2 Progressive discovery

**Rule.** No information is presented before it is needed, and nothing is presented that is not needed. [R]

**Intended flow.** [F]

1. On connection an agent receives the tool's name, a short description and the list of operations: 672 bytes in the build.
2. An agent that wants a command's shape asks help, one level at a time.
3. An agent that sends a wrong command receives the reason and the command that would be accepted.
4. An overlay's schema is read from the overlay's definition in the map when the agent goes to write that overlay.

**Rationale.** [F] The tool's whole definition is placed in front of a model before its first call. Earlier, that definition was about twelve kilobytes and restated one simple shape for every operation. An agent that never wrote still received all of it. The correction mechanism already teaches each shape at the moment of need, so the long definition repeated it at a cost.

**Boundaries.** [R] Validation concerns the shape and integrity of a command. It never judges what an intake inferred. An agent added a rule that refused a purpose for its wording; the founder rejected it, and it was removed.

**Listing overlays.** On 2026-11-03 the founder described a command that lists overlay names, and the content of one overlay when named. On 2026-11-09 he stated that an overlay is a schema object and nothing more. From that, an agent decided that reading the internal root serves the purpose and no separate command is needed. That is an engineering decision, not the founder's. [I]

**Known departures in the build.** [F] Two refusals hand back no usable command. `search` is absent. The root `collection` is accepted. Some answers hold counts of zero; counts are the founder's design, and whether a zero count is shown is not stated. [U]

## 12. Task-relevant context and information boundaries

- **Relevance is positional.** Knowledge attaches to the element it concerns. An agent placed at an element receives what is linked there. [F]
- **Delivered once.** What an agent has already received in a context is not sent again; a repeated visit names what is unchanged. After a reset the agent can read it again. [F]
- **Overlays scope knowledge.** Where an overlay is laid on and where it is masked decide where its knowledge applies. This is designed and not built. [F]
- **The shape first, detail on request.** The whole-map read gives addresses and dependencies with no detail. [F]

**Reducing irrelevant context is not the same as withholding needed information.** [R] The rule removes what an agent does not need yet. It does not remove what an agent needs to act correctly:

- A command that would break the map is refused, with the correction. That is never omitted.
- The shape of any command can always be asked for.
- A delete that would leave a dependency pointing at nothing is refused, with the command that removes the dependency first.

- **By ticket as well as by position.** A ticket is tied to a functionality, and taking the ticket selects the agent's context as going to the element does. An agent need not travel to reach context. [F: the ticket mechanism is outside the base.]
- **Without that mechanism,** an agent is told to locate the functionality in the map before it works on a part of the system. [R]
- **A summary, not the records.** What arrives at an element is a summary sheet: counts of records and the front matter of skills. The agent chooses what to open. [R]

**Unresolved.** [U] Whether a count of zero is shown.

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
- A statement is not decided until the founder decides it. An agent's recommendation is not a decision.
- The founder's intent is recorded in the writer's words with its reason, not by quotation.
- The intake procedure, the schema and the tool contract are changed only on the founder's direct instruction. The founder has stated that tooling may be made more efficient; the semantics may not be changed.
- Preserved source material in the repository is read and not edited. The founder's own folder is not edited.

**Procedure.** [I]

1. State what changed and who decided it.
2. Find every statement and component the change touches, including this document's glossary and section 17.
3. Compare the change with the principles in section 5. Report any conflict to the founder before applying it.
4. Apply a rename in one pass across tooling, and report each place it could not be applied.
5. Keep what is unresolved visible in section 18. Do not remove a question because work has moved on.
6. Record what the change did not cover.

## 15. Building from and evaluating work against this specification

### 15.1 Building

- Work on the semantics is the founder's. Work on tooling fits the semantics. [R]
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
| Use the feature overlay to show one feature at a time | Compliant | The founder's description (7.3, 9). |
| Let an overlay bring its own panel into the interface | Indeterminate | Not established (9). |
| Define a new map overlay at a two-segment address beneath the internal root | Compliant | An overlay's address may have several segments (6.3). |
| Add an operation that starts or ends an intake | Non-compliant | No ceremony in the tool (5, principle 14). |
| Add a check because it seems prudent, with no observed failure | Non-compliant | Principle 13. |
| Copy an outside library into the repository for the interface | Non-compliant | Principle 12. |
| Give an outside party a role, or put the intake's term for it in an address | Non-compliant | Section 6.1. |

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
| The purpose and function fields | `op` and `ef`; goal and function; `why` and `how` | `why` and `how` are the founder's choice for stored names. Not yet run as designed. [U] |
| The direction field | an information flow direction with send, receive, both; intent; `direction` with inbound, outbound, two-way | The last is in the build. |
| Roles | DE, SE, NE and an outside party; Definitive, Supportive, Notable, Divergent | The four words are in the build. |
| The S role | Substantial Element; Supportive Element | Supportive, decided 2026-11-03. |
| The outside party | named by a legal term for a beneficiary in the procedure texts; "downstream party" on pages | An intake term only. It has no role and names nothing in an address. |
| Attaching an overlay to an element | link; block, now mask | Link is the founder's word. |
| The person who directs the project | owner; founder | The founder prefers founder (2026-11-07). The repository's guidance files still say owner. |
| The map | topogee map; metaform | A map is a metaform. "Topogee map" means a different thing and is rejected. |
| The name read from the address | `name_length` (a count); `technical_name` (the words) | The second is in the build. |
| The intake procedure's title | Two different titles in two texts | [U] |
| The project's writing standard | TASTE, with an earlier and a later expansion | The later one, Technically Accurate, Simple, Transparent English, is the one in the repository. |
| Adding functionality to a finished map | refine; the map grows; expanding the functional map | Refine is rejected. The founder has not chosen one word. [U] |
| Base navigable surface | A term of the commissioning task | Not defined by project evidence. [U] |
| Feature overlay | The overlay that tags elements by feature | Section 9. |

Spelling as used in the build: `technical_name`, `masked_overlays`, `project-map` for the tool, `un_built` for the status of unbuilt functionality.

## 17. Requirements and behavioral expectations

Each line is an established requirement unless marked otherwise.

**Semantics**
1. Do not alter the intake procedure's concepts, terms, definitions or examples.
2. Do not add rules on top of the procedure.
3. Hold the procedure in the repository as the founder wrote it.
4. Do not gate or judge an intake. Do not grade a map.
5. Keep the map shallow and coarse.

**Tool and server**
6. One tool, with a list of operations, well under one kilobyte.
7. Present no information before it is needed and none that is not needed.
8. Answer a wrong command with the reason and the command that would be accepted.
9. Provide help that shows how to ask for the form of any other operation.
10. The server handles the intake procedure. [Form unresolved.]
11. The server's instructions tell agents to give the person the interface's address.
12. An overlay is defined beneath the internal root; its definition is its schema and the complete input validation for its records.
12a. The tool has no start and no stop for an intake.
12b. Add a check only to fix an observed failure.
12c. `goto` returns a summary: front matter and counts, not whole skills or records.
12d. Keys are lower camel case in the store and snake case for agents.
12e. Anything keyed by a unique name is a dictionary.
12f. The tool reads and writes data; command-line commands stay out of it.

**Implementations**
13. Rust, Node and Python serve the same purpose under one requirement.
14. Rust takes a more modern approach than the other two.
15. All three present elements with fields together to agents and store by field.
15a. Writes are queued, with fair queuing.

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
26a. The page follows the database continually, with no reload.
26b. A click on a box zooms to it and its direct connections.
26c. Keys show one feature at a time, zoom through levels, start a tour and open the list of keys.
26d. No outside library is copied into the repository.

**Working practice**
27. Record settled matters; keep questions open.
28. Interpret the founder with the reason; do not quote.
29. Match every claim of status to its evidence.
30. Improve by changing one thing at a time and measuring the same things each time.

## 18. Open questions, ambiguities, and decisions needed

An earlier draft listed nineteen questions. A full reading of the founder's 1,089 messages showed that he had answered ten of them. Those answers are now in the sections above. What remains:

**Semantics**
1. The gap fill of the pure text (section 6.4) leaves two points for the founder. First, the pure text says the namespace excludes elements that answer to who, and a downstream party answers to who. Second, the pure method starts at the Defining Element and has no step that records the downstream party's purpose for it. Until the founder accepts a gap-filled text, no intake run in this repository is evidence about his procedure.
2. Do plain stored names for purpose and function hold when the procedure keeps its concepts? One run each way on the same artifact and model would answer it. The founder asked for a hard decision on this.
3. What does a dependency hold beyond purpose, function and direction?
4. What is the one word for adding functionality to a finished map?

**Overlays**
5. Is the internal root renamed with the overlay? The founder renamed the concept and the two arrays; he did not name the root.
6. How do sources fit as an overlay?
7. Is a separate command for listing overlays still wanted (section 11.2)?

**Server and tool**
8. In what form does the server handle the intake procedure? Recommendation in section 10.
9. Is a count of zero shown in a summary?

**Web interface**
10. What technology is the new interface written in? Recommendation in section 7.6.
11. What are the rules and measures of the easing and zooming system? The founder set the aim and asked the agent to design it and to improve it by iteration, so this is the agent's work to propose and the founder's to accept.
12. What belongs to the base surface, and what is added to it?
13. What does reuse by another project mean: which project, what is reused, what the adopter supplies, and how it is taken?
14. May an overlay bring its own view or controls into the interface?

**Scope**
15. What is the interface between this repository and the scoring and mutation pipeline?

**Decided and not applied.** These are not questions. They wait for the founder's instruction on when to apply them: the names dependency, overlay, `overlays` and `masked_overlays` in the tooling; the removal of the root `collection`; the `search` operation.
