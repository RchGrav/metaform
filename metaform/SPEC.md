# Topogee Specification

**State:** in progress. The founder has not reviewed this document. Updated 2026-11-02 with the founder's decisions on roles, names, storage, the form and layers. Updated 2026-11-03 with the founder's decisions on the functional map server, reads, search and layers. Those are recorded as positions 1–23 in `metaform/docs/designs/metaform-server.md`, and the build of them is in `metaform/docs/designs/metaform-server-design.md`.

This document is the specification that the build follows. It starts with the part being built now and grows section by section. Material from `metaform/SPECIFICATION.md` enters only when a section is built and the founder accepts it. Until then, `metaform/SPECIFICATION.md` is a draft and this document does not depend on it.

## Changes of 2026-11-12, which the sections below do not yet show

The founder's instructions of 2026-11-12 aligned the tool with the intake procedure (`rich/intake_best.xml`). The Rust form is changed. The Node form, the Python form and the conformance set are not changed yet. Where a requirement below disagrees with this list, this list governs.

- **`wants` is an array.** An element holds its wants in `wants`, an array with one record for each providing element (PE). Each record holds `pe`, the address of the providing element, with `op`, `ef` and `ifd`. **Reason:** a plural name holds an array, and an object under an element is always an element beneath it. The stored map nests elements as objects at every level of the path, so an object that held records would have to be told apart from a branch by guessing at its field names. The earlier form did that, and the guess is removed.
- **The field name stays `wants`.** For part of 2026-11-12 the field was renamed `dependencies`, on the founder's instruction, and the founder then reversed it. **Reason:** `wants` says what the record is, a want of the receiving element; it reads as a verb and as a plural noun; and it was tested as the field name and inferred correctly. `dependencies` was not tested as the field name. "Dependency" remains the word for the concept in prose and in the roles `UD` and `DD`.
- **Want fields.** A want has `op` (Operative Purpose), `ef` (Encounter Function) and `ifd` (Information Flow Direction). They replace `why`, `how` and `direction`. `ifd` is `send`, `receive` or `both`, relative to the receiving element. **Reason:** these are the procedure's own terms, and a model infers from them.
- **One want for each providing element.** Within a receiving element, a providing element with its `op`, `ef` and `ifd` is one set. A receiving element may hold any number of wants, and a providing element appears once among them. A command that names the same `pe` twice under one element is refused. **Status:** decided by the founder, 2026-11-12.
- **Roles.** A role is `AT`, `DE`, `SE`, `NE`, `CQU`, `UD` or `DD`. They replace Definitive, Supportive, Notable and Divergent (R-3.13). A map may hold several Defining Elements, so the rule of one Definitive element is removed. `map` returns `defining`, the list of the project's Defining Elements, in place of `definitive`. **Reason:** the intake gives a Defining Element to each artifact type it finds.
- **`refs`.** An element holds `refs`, an array with one uri for each artifact that has the element's address. It replaces `uri`. A code project is one artifact and has one uri. Several photos of one type share one address, and each has its own uri. `refs` is a field of the element, not a layer, so every read of the element returns it. **Reason:** the map holds each address once, so the artifacts that share an address must be listed at that address.
- **Reads.** A plain read returns the element's own fields and no wants. `goto` returns the element, its `wants`, and `wanted_by`, an array of the wants that name the element, each with `re`, the address of its receiving element. A raw dump returns everything stored at a path. `map` returns every address, including the layers beneath `layer`, and each want as a pair. **Status:** confirmed by the founder, 2026-11-12.
- **The layer root is `layer`.** It is singular because it is a root in the namespace and not an array. The founder said so on 2026-11-12, after R-6.28 recorded the name overlay on 2026-11-11. Whether R-6.28 still stands is open.
- **Refusals that return the corrected command.** A command with `uri` is refused with the same command using `refs`. A command that gives `wants` as an object keyed by address is refused with the same records as an array. An `ifd` of `sends` or `receives` is refused with `send` or `receive`.
- **Stored maps.** A database made by an earlier build is brought up to date when it is opened: the stored relationship `WANTS` becomes `DEPENDS_ON`, and its fields `why`, `how` and `direction` become `op`, `ef` and `ifd`. No agent sees the name of the stored relationship. A stored `uri` is read as `refs` with one item. Stored role values and `ifd` values are not changed.
- **Open, for the founder.** Whether a write takes one want at a time under the singular word `want`, which the founder suggested on 2026-11-12. The build accepts the `wants` array in a write.

## How to read this document

Every requirement carries one status:

- **Decided:** the founder stated it. The source gives the founder's words.
- **Proposed by the founder:** the founder wrote it in a working document, such as the documentation set in section 11, and has not confirmed it as final.
- **Proposed:** an agent proposed it. The founder has not confirmed it.
- **Open:** the founder must decide it. It is listed in section 10.

A question from the founder is not a decision. Record it as Open until the founder answers it.

Do not build a Proposed or Open item as if it were Decided. If a requirement is wrong and blocks the work, do it right, record the deviation and tell the founder at once. Do not let it hold up the work.

**Status:** Decided. **Source:** "Spec comes first until it's wrong... Do it right. Document it. Let the user know right away. But don't let it hold you up."

This document contains no analogies. Words such as "must" apply to the implementation.

## 1. Purpose

This specification covers Metaform, the context tool for development agents, with the chassis and the feature modules. Topogee, the shared world, is specified in `docs/designs/world-system-spec.md` (`DECISIONS.md`, "Naming: Topogee and Metaform").

Metaform is a functional topology. It forms intake from intent, for a greenfield project, through to a brownfield one, for any kind of project, code or not. It can take in a specification, refine and organize it, and save it again in an improved form. It can take in a project whose code is hard to refactor and serve as a formboard that agents use to realign the code base. Inside any project, it is a context management system.

**Status:** Decided. **Source:** the founder: "I suggest calling metaform a functional topology capable of forming intake from intent, greenfield, to brownfield or any type of project code or not code. its capable of importing (performing intake on) a specification, refining and organizing it and resaving it in an improved format, additionally it can be used for performing intake on projects with code that is difficult to refector and acting as a formboard for agents to realign the code base, as well as being a context management system inside of any project." (2026-11-07). `TOPOGEE.md` is the opening statement; it uses "Topogee" for Metaform.

The Metaform is the functional form of a project. It records what the project does and how its functionality connects. It is not a record of code. Code, a user manual, a specification and a screenplay are all evidence of functionality.

An agent that understands what a thing is can change it safely. Intake supplies that understanding before any mutation starts.

**Status:** Decided. **Source:** "Before anything can mutate it needs to fully understand what a thing is."; "its not the code being analyzed its the functionality".

**R-1.4** The cost that Metaform saves is a reasoning cost. An agent has a finite amount of reasoning: a limit on how many things it can track and understand at once. When an agent enters a project it must orient itself, and orientation uses part of that reasoning and wastes context. Even after orienting, an agent usually does not get the whole picture, because its attention is on the detail in front of it. Metaform gives the agent a view of the whole project in every direction, together with the thing it works on. The map's addresses are named so that they lean on primordial type understanding: what a model already knows about kinds of things, which it recalls before it starts to infer and so without the cost of orientation. The reasoning that orientation would have used is kept for the work itself. Metaform does not raise a model's abilities. The improvement comes from reserving what allows an agent to perform well. The saving is not a saving of tokens or of money. A token count may fall as a result, and it may be measured (R-1.3), but it is not the purpose and it is not how the benefit is stated.

**Status:** Decided. **Source:** owner statement, 2026-11-09, restated here. **Reason:** documents and agents kept restating the purpose as saving tokens. That is a wrong inference: the limited resource is the reasoning of the model the agent runs on, not the price or the count of tokens. `metaform/docs/metaform-concepts.md` ("Inference amortization") says the same.

**R-1.2** Metaform works on greenfield and brownfield projects and anything in between. It ingests the intent of a system that exists. It is also a place to construct and refine intent for a system that does not exist yet, and it exports that intent back into a specification. A specification can make the round trip: its intent is taken in first as the base map, then its materials go into categorical knowledge layers, it is refined, and it is exported again. That structure is what a roundtable works on together.

**Status:** Decided. Not built. **Source:** "its always been designed as a greenfield/brownfield or anywhere in between approach"; "imagine the system not only being able to ingest a systems intent, but also being able to be a place where you construct and refine intent and then have a function to export it back into a specification, or even round tripping a specification in, first its intent and then its materials into categorical layers, it provides a structure of understanding and refinemenet which a roundtable could operate on together" (2026-11-06). The layers that make up a project's specification are recorded with the project's details in the main database, so a user never needs to know or name them ("have the layers that make up the specification in main db as project details the user should not need to know what the names of the layers are that constitute what the specification is.. first of all how would they even know", 2026-11-06). The export itself is designed in `metaform/docs/designs/specification-round-trip.md`. A specification's materials first enter the layers by inference, as its intent enters by intake: an agent reads the source, decides which element each part describes, and writes it as blocks with `update` (owner, 2026-11-09: "the initial import is a matter of inference"). The CLI import is only the return trip: it reads back a document that the export made, and refuses any other.

**R-1.1** If the specification states how a foundation must work, build that foundation. Do not build a temporary foundation and plan to replace it. Prototypes may test ideas, but nothing is built on them.

**Status:** Decided. **Source:** "if we know the specs of how something needs to work then why dont we just build that foundation right.. its easy to leave the wrong foundatiuon in place and really regret it later. So its kinda a rule I want to stick to."

**R-1.3** The system counts the tokens that reach each agent from everything the system controls: tool schemas, context, skills, tasks and messages. The count need not match any model's tokenizer exactly, but it must be consistent and comparable across runs. A change can then be measured against the version before it, and an agent working with Metaform can be compared with one working on the same task without it.

**Status:** Decided in principle: "measured or honestly estimated context usage" (`DECISIONS.md`, settled requirements). The method is Proposed by the founder: "I will even propose during development we devise some method that tracks performance and a token count that hits agents for everything we control. It doesnt need to be precise to the count of the exact number of tokens but it must be consistent and comparitive" (2026-10-30). **Reason** for the comparison with and without Metaform: it is the evidence for the preprint's central claim, inference amortization, and the founder intends Metaform to stand as an open-source tool and a preprint (2026-11-07). The count is an instrument for comparing runs. It is not Metaform's purpose, which R-1.4 states.

## 2. Two surfaces

The system has two surfaces. They are separate designs.

| Surface | Who uses it | What it is |
|---|---|---|
| The form | Agents | One tool, its commands, and the fields that agents fill out. |
| The store | The system | The databases and their structure. |

**R-2.1** Agents use the form. Agents never see how the store is structured.

**R-2.2** A requirement on the store must not add a term to the form.

**Status:** Decided. **Source:** "you cant start confusing what the agents have for forms and how we store and structure the data."

### System structure

**R-2.3** The system has a chassis and modules. Parts of the core system are realized as modules. These are base modules.

**R-2.4** New features are modules that use the base system. A feature module does not change this specification.

**Status:** Decided. **Source:** "there can be base modules.. parts of the core system are realized as modules."; "we can develop features that use the base system without touching the spec."

**R-2.5** This specification defines the chassis and the base modules. Each feature module has its own document.

**R-2.6** The parts are assigned as follows:

| Part | Holds |
|---|---|
| Chassis | The store and its data access, events, settings, the module contract. |
| Base modules | The MCP server and the form, the layer resolver, intake, the Composer, the Facilitator, the ACP harness. |
| Feature modules | Mutation families, the web interface, the world engine, and later features. |

**Status of R-2.5 and R-2.6:** Proposed. The row for base modules is replaced in part: the MCP server and the form are the functional map server of section 4.2, which is not the chassis (R-4.4).

**R-2.9** The functional map server and the chassis work together when both are present. The chassis is part of a larger vision. It can hook the functional map server, and messaging can be one of its modules. The functional map server brokers for the other parts of the system.

**Status:** Decided. **Source:** "the shape I want is so they work together when both are present.. the chassis would need to be able to hook the metaform mcp server"; "the mcp server needs to be able to broker for the other parts of the system which is my I say it has a running back end". What the hook carries is not specified yet.

**R-2.11** Presence decides who controls data. At start-up, a module checks whether a chassis is present. If one is, the module uses the chassis as its data source for the parts that matter for deep integration, and keeps the rest of its data itself. With no chassis, the module stands alone; the functional map server is then an ordinary MCP server that a harness can use. Control is decided only at start-up, never handed over while running.

**Status:** Decided. Not built. **Source:** "is there a way that we can have a module relinquish its ownership of its data to the chassis when its present, like for the mcp server.. the mcp server can act standalone without mcp and just be like any other mcp server"; "it would be based on presence.. the point is allow the mcp server.. to pass control of just the parts that need to be managed by the chassis.. on startup the module decides is there a chassis, and if so it uses it as a datasource, but just for the part that matters for the deep integration the mcp can still keep some of its data when there is no point K.I.S.S.". Which parts move to the chassis is decided when the chassis is specified. The boundary and the module declaration are Proposed, in `metaform/docs/designs/metaform-server-design.md`.

**R-2.10** Only one agent performs intake. More than one agent runs only under orchestration. Orchestration reads the map and never changes it.

**Status:** Decided. **Source:** "the only place multiples would be running is when multiple are orchestrated only one agent performs intake"; "orchestration refers to the map any writing doesnt need to change the map the map should be durable info".

**R-2.7** A module reaches the chassis only through what the chassis exposes. Every part of the chassis that is exposed to a module must be:

1. defined;
2. available in the template module;
3. documented.

Nothing is exposed until all three are done.

**Status:** Decided. **Source:** "any part of the chassis we expose to a module we create we must define it and make it available in the template module and document it."

**R-2.8** A check fails the build if a chassis export is missing from the template module or from the module documentation.

**Status:** Proposed.

## 3. The map

**R-3.1** A project is a nested tree of elements. Each element lives at one address.

**R-3.2** An address is a dotted namespace path, such as `code.engine.game`. Each segment names functionality.

**R-3.3** The valid root scopes are `code`, `document`, `media`, `data`, `collection`, `upstream`, `downstream` and `layer`. `upstream`, `downstream` and `layer` are root prefixes: they hold what is not located in the project, and the segment after one of them can be another root scope. `upstream.code.engine.physics` is physics engine code that the project relies on (R-3.7). `layer.document.specification` defines the specification layer (R-6.24).

**Status of R-3.1 to R-3.3:** Decided. **Source:** `TOPOGEE.md`; `intake-new.md` version 3.1. The documentation set lists six root scopes, without `collection`. That is decision D-11. `layer` was added on 2026-11-09: the owner decided that a layer is defined by an element in the main map, such as `layer.document.specification` (relayed by Jorge, the store agent; see R-6.24). `layer` is a root of its own, like `upstream` and `downstream`, because a layer definition is not located in the project. Placed under a project root such as `data`, it would mix with the project's functionality and read as part of the project (owner, 2026-11-09). Intake places nothing in `layer`: intake infers no layers, so the intake procedure does not list `layer` (owner, 2026-11-09). Root prefixes: the owner, 2026-11-09: "all three of them are root prefixes, so stuff under them can be the roots".

**Correction to R-3.3, owner, 2026-11-09. Recorded here; R-3.3's text, the code and the intake procedure are not adjusted yet.** Intake has six roots. Four are the root types of a project: `code`, `document`, `media` and `data`. Two hold what is outside the project: `upstream` and `downstream`. `collection` is not among them. `layer` is not an intake root. It is internal: a schema root that defines the layers and validates what is written to them. **Reason for `layer`:** intake infers no layers, so a layer definition is not something intake can find in a project. The owner's reason for leaving out `collection` is not recorded yet. **What `layer` holds, owner, 2026-11-09:** `layer` holds what intake leaves out. A programming language is a medium and not a functionality, so it has no address in the map, and it is defined as a layer: `layer.code.cpp`. A root type can therefore follow `layer`. **Open:** the address of the specification layer. The owner gave `layer.specification` as an example the same day, and the build defines it at `layer.document.specification`, which has the form of `layer.code.cpp`. An agent's earlier reading here, that no root type follows `layer`, was wrong and is withdrawn.

**R-3.22** A prompt can be expanded in width. The usual metaprompt expands in depth: one prompt becomes a more detailed prompt. In Metaform, one instruction is applied at every element of the map, and each element answers it for its own functionality. The answers form a layer (R-6.18). An example: for each element, add what a developer should foresee about memory management there.

A layer can exist for one piece of work. To port a project from C++ to Rust, a porting layer is added, such as `layer.code.port.cpp_to_rust`: at each element, what an expert developer would keep in mind while porting it. When the port is done, the C++ layer and the porting layer are removed and a Rust layer is added. The map does not change. Names under `layer` are not bound by the intake's naming rules, so a layer may be named freely.

**Status:** Decided. **Source:** owner statement, 2026-11-09, restated here. **Reason:** it is the second sense of "meta" in the name. The first is that functionality is a higher order of abstraction, one step removed from the thing that performs it.

**R-3.4** An element's fields are `technical_name`, `name`, `role`, `uri`, `status` and `wants`. `technical_name`, `name` and `role` are mandatory. `uri` and `status` are optional. A want record holds `why`, `how` and `direction` (formerly `intent`, R-3.6).

**Status:** Decided. **Source:** the founder's documentation set, module 3.1. This replaces `name_length`, `id`, `project`, `goal`, `function` and `ice`. `why` and `how` replaced `goal` and `function` everywhere on 2026-11-07 (`DECISIONS.md`, "Want fields are why and how"); `ice` was removed from the intake, schema, contract and code on 2026-11-07 (R-3.14). `technical_name` and the four roles were aligned on 2026-11-07 (`DECISIONS.md`, "technical_name and the four roles").

**R-3.18** An address follows these rules:

1. Split on `.`, reverse the segments and read underscores as spaces. The result must be a sound industry-standard noun phrase, and each child takes its parent as its trailing noun. `code.buffer.ring.packet` reads "packet ring buffer code".
2. All artifacts are entities, and all entities are elements.
3. The address narrows from trunk to leaf. Each child segment is a functional subtype or part of its parent, never an encoding such as `.jpg` or a genre such as `.platformer`.
4. A concept whose prefix is a valid functional type on its own is split with periods, as in `code.engine.game`. Words are joined with underscores only when no word is a valid prefix alone, as in `code.queue.dead_letter`.
5. Segments use standard practitioner terms. Coined words, slang, marketing labels and arbitrary abbreviations are not allowed.

**Status:** Decided. **Source:** the founder's documentation set, module 2.2.

**R-3.10** No element has a `project` field. A project's name lives only in the main database (R-4.1).

**Status:** Decided. **Source:** "Why would we have a field name at all named project? That doesn't make any sense for our design at all."

**R-3.11** `technical_name` is the industry term for the element. Its words must equal the same number of leading words of the reversed address, with underscores read as spaces. For `code.buffer.ring.packet`, the reversed address is "packet ring buffer code", and "packet ring buffer" passes.

**Status:** Decided. **Source:** "yes technical name counts words correct". The purpose: "the technical_name now acts as better inference and proofs the name space address".

**R-3.12** `name` is the project's own name for the element. It must not equal `technical_name`.

**Status:** Decided. **Source:** "the new spec is they differ"; "the whole purpose of having both is ease of location". **Not enforced by the tool; open as D-19.** The intake procedure lets `name` be the standard term when the project has no name of its own for the element (`Intake.md`, Namespace Rules 1). The tool refused an equal `name` for part of 2026-11-09. In four test intakes that day, every agent was refused at an element with no project name, mostly a downstream party, and every agent then invented a name, which the procedure forbids. The refusal was withdrawn the same day for that reason (R-5.20: logic is added only to fix an observed issue, and this logic caused one).

**R-3.13** Every element has one of four roles:

- **Definitive:** the element of the artifact under examination whose loss causes a mutation, meaning it no longer allows the artifact to remain what it is.
- **Supportive:** an indivisibly coupled element whose function is meant to assist the definitive element.
- **Notable:** a discrete, structurally independent feature or specialized exception case that possesses unique systemic significance.
- **Divergent:** an unaligned, weak, or redundant element captured during intake that deviates from the core architecture. This role must be investigated on the purpose it is serving, and either be realigned as repaired or improved, or ejected.

A project has exactly one Definitive element.

**Status:** Decided. **Source:** `roles.md` in the founder's folder; "those are the roles. Those are what I worked out."; for the single Definitive element, "there is only one". These replace `DE`, `SE` and `NE`. The old SE definition covered both an element that assists and one that is weak or should be improved. Those are now Supportive and Divergent.

**Which elements the one-Definitive rule counts:** only the project's own elements, not those under the root prefixes `upstream`, `downstream` and `layer`. `map`'s `definitive` names the project's Definitive element by the same rule, and so does the root rule of R-6.26. **Status:** Decided, engineering decision by Marcus (2026-11-09), following R-3.3 and R-3.7; not an owner decision. **Reason:** R-3.3 says the root prefixes hold what is not located in the project, and R-3.7 says `upstream` and `downstream` are not part of the project being mapped, so R-3.13 is about the project's own Definitive element. Without this rule, an element under `upstream` or `downstream` whose role is Definitive would block the project's own Definitive element and every write that touches either. Built in `names::in_project` and `reads::is_project_definitive`.

**R-3.20** The Definitive, Supportive and Notable roles form a hierarchy. The base map is the skeleton: it holds functionality only. Detail is kept out of it on purpose, so that knowledge layers can fill in what the core functionality cannot describe alone, built around the skeleton.

**Status:** Decided. **Source:** "my intent with the knowledge layers and the structure itself and the defining elements, supportive elements and notable elements ... that is a hierachy, and knowledge layers allow filling in details the core functionality cant describe alone, there is a reason why that detail is kept out and its so it can use the knowledge layers to construct it around the skeleton" (2026-11-06).

**R-3.14** Coupling is the Supportive role. No want carries an `ice` field.

**Status:** Decided. **Source:** "ICE was superceded"; "the DE <-> SE relationship is the inseperable boundary" (2026-11-07); "I'm even saying drop ice"; "Supportive means coupled."; "it removes it from being an extra field, and it puts it into a category".

**R-3.15** CQU is an intake term for inference. It is not a role, and it never appears in an address. A downstream party is named by its type, such as `downstream.developer.game`.

**Status:** Decided. **Source:** "CQU was never a role."; "Can't you freaking name the type of party it is?"; "It's just for inference."

**R-3.16** The map holds durable knowledge: element identities, `wants`, `sources`, `skills`, durable engineering invariants and verified architectural review gates. Ephemeral knowledge, such as investigation notes, drift observations, temporary debugging flags and coupling theories, goes in a ticket and never in the map.

**Status:** Decided. **Source:** "The map is really for stuff that is durable, and long-lasting"; "If we need something like that, we'll have it write a ticket for it."; the founder's documentation set, module 1.1.

**R-3.17** Each `why` and each `how` is one sentence fragment. It states what happens, without tunable values.

**Status:** Decided. **Source:** "All goal and function language should be no more than a sentence fragment"; "after should have been this Monitors context window use over the ACP session." The documentation set gives the grammar of each field (R-6.17).

**R-3.5** A want record belongs to the receiver, the element whose purpose its `why` states. The key of the record is the address of the provider, the element whose service to the receiver its `how` describes.

**R-3.19** The two ends of a want are this element, where the agent stands and which holds the want, and the other element, which the want names. The system reasons from where the agent is operating.

**Status:** Decided. **Source:** "this element and the other element"; "the whole system reasons against where an agent is operating"; "lets lock it in". `originator` changes sides with the flow, so it is not used.

**R-3.23** The record that an element holds for another element it relies on is called a dependency. The address of the record is the dependency. Its Operative Purpose is the purpose for the dependency, and its Encounter Function is the function of the dependency. The name replaces `wants`, and before that `join`.

**Status:** Decided by the owner, 2026-11-11. Not applied: the procedure, the schema, the tool contract, the stored field and the pages still say `wants`. **Source:** "instead of join could just call it dependency"; "Everything inside of dependency is our OP for the depencency the function of the dependency and the address of the dependency"; "software doesnt have wants, So dependency lands better"; "in a story or script the plot can have a dependency in the mcguffin   it works we should just go with that". **Reasons the owner gave:** `wants` is a verb, and it was chosen because a person does not have a dependency on a photo, which the owner now calls the wrong measure; `join` is a database term, taken from the reified hypergraph the structure was first thought of as, where logic can exist in a join.

**R-3.6** `direction` has three values: `inbound`, `outbound` and `two-way`. They are relative to the element that holds the want, not to the project. The request is never the direction. The field was called `intent`.

**Status:** Decided. **Source:** "I thought we would make the third value send_receive"; "not including the request". The values replace `send`, `receive` and `send_receive`. **Source:** "inbound outbound two-way"; "add outside of the project to those and its all hunky dorey in my book". The field name `direction` replaces `intent`. **Source:** the founder, 2026-11-08. **Applied 2026-11-09** on the founder's instruction to the intake procedure (`Intake.md`, `Intake.xml`, `intake.mmd`), the schema, the tool contract, the proposed skill, the canonical map, `roundtable/metaform.json`, the Rust server and the Node harness. The Rust store's `WANTS` column is now `direction`. A database created before this change still has the `intent` column and must be cleared and rebuilt (§9). The Node harness keeps its `intent` column so that its old databases still open.

**R-3.7** `upstream` is what the project relies on, outside of the project. `downstream` is what relies on the project, outside of the project. Neither is part of the project being mapped.

**Status:** Decided. **Source:** "its not part of this project we are working on".

**R-3.8** If functionality changes, it is a new node. The map grows. Agents who work on an element only mutate it.

**Status:** Decided. **Source:** "if they change functionality, it's no longer the same functionality, it's a whole different node. The map grows."

**R-3.9** Protection against transformation comes from the type understanding that intake records. No frozen-core field exists.

**Status:** Decided in principle. **Source:** "my process found a way to protect a thing that relies on the type understanding". How an agent receives this boundary is not specified yet.

**R-3.21** Type understanding is a relationship of three parts: the why of the receiver, the how of the provider, and the what of the functionality. The address states the what. A want states the why and the how (R-3.5). This is the exact relational identity that the preprint defines as `C(T)` (`metaform/docs/preprint/preprint-v1.0.md`, section 6), and that definition stands as written. Every element has this relationship. An element may want nothing itself, but something downstream always depends on it. If nothing did, it would not be a type.

One such relationship is an anchor. Many are a formboard: together they are the shape that agents realign a code base against (section 1). The anchor is not removed and it is not made unnecessary: it is what protects an element against transformation. The anchor also has uses beyond protection, which are not specified yet: ideation and creativity, and a surface on which an agent experiments to seek improvement without guidance (owner, 2026-11-09).

The skeleton is not the whole of a thing (R-3.20). The skeleton keeps a thing the kind of thing it is. The qualities that make it the particular thing it is are kept in the knowledge layers.

**Status:** Decided. **Source:** owner statements, 2026-11-09, restated here. **Reason:** it says what R-3.9's protection consists of, and it keeps the protection separate from the detail: the skeleton prevents transformation, and the layers hold what the skeleton leaves out on purpose.

## 4. The store

### 4.1 Storage

**R-4.1** Maps are stored in LadybugDB. A map is the logical unit: it has its own map id, its own write queue (R-4.7) and its own identity. A database is the physical unit that groups maps. The home is the folder that one functional map server owns and writes under (R-4.4); this project's `.mcp.json` uses `~/.metaform-rust`. A project's main map and its chained maps are partitions of the project's database, `projects/<encoded-path-id>/project.lbug`. Maps that belong to no project are partitions of the home's standalone database, `maps/maps.lbug`. A map moves to its own database when it needs its own writer, its own sharing or its own size; a map run as its own instance (R-4.14) has its own home and so its own database. Rust code works through Ladybug and never writes map files itself. Settings and the project registry may be JSON. Nothing is written into a project's own folder, and a project's database never stores the project's name.

**Status of the grouping (2026-11-07):** Default, for the founder's confirmation. It replaces "one database per map", which read the founder's "any element in the metaform map can be given its own db" as a rule rather than a capability. One process failed at about 7 Ladybug databases on default settings, so a database for every map would not scale. The design and evidence are in `docs/designs/storage.md`, section 2.2.

**Status:** Decided, correcting the earlier text "All data lives in the Metaform home, `~/.metaform`, as JSON files" (recorded 2026-11-03). The founder never decided JSON for the map: the record took a conditional "yes" about the live server ("So long as that map can have a live running server that tracks all of the projects and can be a sink for each agents mcp server then yes ... that must be the foundation of it") as a storage decision. **Source:** "who the fuck is storing shit in json?!" and "in metaform rust doesnt write to disk" (2026-11-07); "the current rust version isnt limited to a single project db, and db's can represent sub features ... any element in the metaform map can be given its own db" (2026-11-07); "our data structures will have a graph shape in ladybug w/ cypher" (`docs/owner-explanations.md`); "settings and project registry can be in json obviously" (2026-11-03); "The database shouldn't say what the project name is. Only the core database does"; "Each project's database should be named exactly the same." The folder layout under the home is Open (D-17).

`METAFORM_HOME` replaces the home when set. **Status:** Proposed. The founder did not decide it: "I never authorized an override, but I dont have an issue with one UNLESS its a blocker". It keeps test runs off real data. **Reconsidered 2026-11-07:** many Metaform instances must run at once, each owned by an agent (R-4.14), and each instance needs its own home. The override is now needed, which meets the founder's condition ("UNLESS its a blocker").

**R-4.8** Every setting is declared in code with its default. A default is never stored. A global value is stored in the main database. A project value overrides it and is stored in the project database. Every lookup goes through one place.

**Status:** Decided. Global settings were built on Ladybug in the Node harness, and project overrides were not built. The values move to `settings.json` (R-4.1). In the Rust server (2026-11-08): settings are declared in code with their defaults (`metaform-store/src/settings.rs`), global values are in `<home>/settings.json` and a project's in `projects/<id>/settings.json`, and the CLI reads and sets them through the server (`metaform settings`, `metaform set`, `metaform unset`), not through an agent tool. The first setting is `stores.max_open_databases`. **Source:** "Every setting the system has would be surfaced as a global setting and would apply to all projects unless they're overrided with a local setting in that project"; "defaults aren't stored. There's no point."; CLI-023 in `RchGrav/metaform-archive`.

**R-4.9** The system is built for many projects from the start.

**Status:** Decided. **Source:** "The mistake we would make is to build this whole system just around only managing itself."

**R-4.14** Many Metaform instances can run at once. An instance is one home with its own functional map server (R-4.4), so instances never share a lock or a writer. An in-game agent can own an instance and use it to plan and design its features. Within one instance, every client connects through the one server and its forwarders (R-4.5), and none blocks another. Metaform is also used inside the game, to design features, worlds and anything else that needs a specification.

**Status:** Decided for many instances and agent ownership. **Source:** "metaform should be able to be launched many copies and have in game agents owning an instance they use for planning and designing features" (2026-11-07); "we cant have it blocking that way thats an out of the gate design flaw" (2026-11-07); "metaform will be used in game to design features worlds or anything that requires a specification" (2026-11-07). The instance-is-a-home model is Proposed. **Reason:** R-4.4 keeps one writer per home, so a separate home per instance gives many instances without contention. The service launcher starts each instance under its owner's identity (`docs/designs/service-launcher.md`). When this was written, the build (the Node harness) implemented neither R-4.4, R-4.5 nor R-4.7: it ran one stdio process per project, held an exclusive database lock, and had no write queue, so a second client could not open a map that another session was serving. The Rust server implements all three (2026-11-07; `metaform/docs/designs/metaform-rust.md`, Progress). The founder: "metaforms current state was not meant to be the full design it was something the agent did with the intent of dealing with write queues later".

**R-4.15** Maps chain, and maps also stand alone. Any element in a map can be given its own map, stored apart, and an agent drills down by following the chain into deeper maps. A map can also belong to no chain: an in-world agent creates private maps for its own projects. A sub-feature can have its own map, and so can an in-game feature that players and agents build outside a project's main map. Each map has its own write queue (R-4.7). A map is the unit of storage and of writing, not the project. Something outside the project's repository appears in the project's map as one element under `upstream` (or `downstream`) that names the functionality, such as `upstream.code.engine.game`, and its `uri` names that repository. That element is a barrier and a reference: the outside project's map is linked inside it, and the element can hold details about it, but neither the element's details nor the linked map is part of the project. The outside project can have its own functional map: a separate map for a different project, with the regular root scopes, in which `upstream` means upstream of that project. Its elements keep their own addresses; `upstream.code.engine.game` in this map corresponds to `code.engine.game` in that one. An agent reads that map only when it asks for it.

**Status:** Decided. **Source:** the founder: "the current rust version isnt limited to a single project db, and db's can represent sub features and the core system will involve map chaining and write queing, that means any element in the metaform map can be given its own db and allow drilling down in deeper.. as well as in game features for players and agents outside from the projects metaform blueprint" (2026-11-07); "not just chained but unchained, ingame agents will be creating private maps for their projects in game" (2026-11-07). Who may read a private map is decided by its owner; how that is enforced waits for agent identity (R-8.2). How a chained map is stored and addressed is a default in `docs/designs/storage.md`, section 2.2: a `Map` node in its parent's database, reached by a `CHAINS` relationship; how chaining relates to links between projects (section 7) is Open (D-16). Outside projects as one element, with their own map: owner decision, 2026-11-09. It corrects two records made earlier the same day, which placed the outside map inside an element and renamed its elements under `upstream`. Elements of the project relate to the outside element through ordinary wants, whose `direction` is whatever the relationship is (R-3.6). **Reason (owner, 2026-11-09):** the outside project's detail never enters the context of an agent that only wants this project's shape, and its whole functional map is still available when an agent decides the extra detail would help. The request that reads the outside project's map from its element is not decided; Marcus and Jorge recommend `{"map": "<address>"}`, which takes an address as `goto` does and answers that map's shallow graph in its own addresses, with `{"map": {}}` staying the project's shape. How that map is stored is open (`dev/chained_map_storage.md`). Where the `uri` is stored is part of the open storage question below. Not decided: whether the chained map's elements are stored under that address in the parent's database or kept in their own database and only shown there (Jorge is assessing separate databases under `stores.max_open_databases`).

**R-4.2** The project name is the root object. If the store is exported to JSON, the path to an element is `$.projectname.namespace.address.of.element`.

**Status:** Decided and built. **Source:** "we need to have the project name in the database as the root object"; "I am referring to the structure we store it if we exported it to json". The export takes the name from the main database.

**R-4.3** Each layer is stored in its own files, apart from the map (R-6.21).

**Status:** Decided. Replaces the earlier proposal of one record per layer member. **Source:** "a layer is indexed by the map as a separate file".

### 4.2 The functional map server

**R-4.4** The functional map server is one long-running process on the home. It tracks every project, and it is the only process that writes under the home. It is not the chassis. Only one functional map server can run on a home.

**R-4.5** Each agent still starts its own MCP process, the forwarder. The forwarder relays to the functional map server. It names its project folder when it connects, and it never writes files. The CLI, the viewer and every outside part reach the data through the functional map server. The server lists every project registered in its home: `metaform projects`, through the admin request `{"admin": {"projects": {}}}`, answers each project's id, name and folder, and registers nothing. One web server per host uses this list to serve every project through one GUI.

**Status of R-4.4 and R-4.5:** Decided. Replaces the chassis as owner of the databases. Project listing and one web server per host: owner decision, 2026-11-09. The GUI must cover many projects, so one web server on a host serves them all through the one process that manages the core database and every project's databases. Listing built 2026-11-09 on branch `project-listing`; the web server is not built. **Source:** "So long as that map can have a live running server that tracks all of the projects and can be a sink for each agents mcp server then yes"; "well its a process its not the chassis as a specified it."; "yeah only one can start".

**R-4.7** Writes go into a queue owned by the functional map server's write manager, one queue for each map (R-4.15). Each queue runs its writes one at a time. The write manager serves clients in turn, so one agent's writes cannot starve another's. Reads run concurrently against the last committed state. A write is acknowledged only after it commits.

**Status:** Decided. **Source:** "well there needs to be a write queue"; "write queues on everything even if its not the chassis itself and fair queuing on writes" (`DECISIONS.md`); "you need to have a write manager for write queues thats a huge design flaw" (2026-11-07). The detail is from the earlier proposal and `metaform/verification/ladybug-spike-2026-10-30.json`. Serving clients in turn is Proposed, as the meaning of fair queuing.

**R-4.10** The functional map server announces each change as it commits. Nothing that shows the map polls for changes.

**Status:** Decided. **Source:** "why would it poll the commands are being applied"; `DECISIONS.md`: "No recurring application polling. WebTransport control channel".

**R-4.11** Agents send and receive snake_case. The store keeps keys and address segments in camelCase. The functional map server converts between them on the way in and the way out. A name that would not convert back exactly is refused with the reason, and a name in uppercase is refused, not lowercased.

**Status:** Decided. **Source:** "normalize to lower and snake to camel and when landing back with the agent camel to snake.. I dont want to see any lint warnings about the underscores"; "thats what input validation is for". The refusal of uppercase was settled during the design review of 2026-11-03.

**R-4.12** The map is stored nested by address segment (R-4.2). Agents see the nested form only through a raw dump (R-5.34; changed 2026-11-09 from "Agents never see the nested form"). Every read, search result and refusal names an element by its full namespace address.

**Status:** Decided. **Source:** "storage is nested, agents see full namerspace addresses, nested is for storage. Agents dont see nested form."

**R-4.16** The map is realized as a graph in its Ladybug database. Every element is a node carrying its fields (R-3.4). Nesting is a relationship from each address segment to its children. Each want is a relationship from the receiver to the provider, carrying `why`, `how` and `direction`. Each item of a layer is a `Record` node reached from its element by `HOLDS`, with its position, so the layer is stored as a structure of arrays (R-4.6). An element's fields are kept in one canonical order: the intake fields in R-6.15's order, then the rest by name; a want record's `why`, `how` and `direction` come first. Agents see only the flat view (R-4.12). *(Records and canonical order added 2026-11-09, Proposed: the owner requires SoA storage and that the JSON dump and every other output match precisely; the layout is Jorge's, in `docs/designs/specification-layer.md`, Storage.)*

**Status:** Decided. **Source:** "its a graph db thats how its realized.. how is anything a table" (2026-11-07); the founder's documentation set, section 5.1, "Nested Storage View (Internal Database State)" (`metaform/docs/documentation-set.md`), which the founder pointed to as the database state (2026-11-07). The database holds 5.1's state with 5.1's names: `technical_name`, `name`, `role` (Definitive, Supportive, Notable, Divergent), `uri`, `status`, `wants` records with `why`, `how` and `direction` (formerly `intent`, R-3.6), and the native arrays `memory` and `sources`. `metaform/metaform.schema.json` (2026-10-31) still uses earlier names and lags 5.1; it is protected and changes only on the founder's instruction. How layers attach to the graph follows the founder's unified layer approach, still to be described.

**R-4.13** *(Superseded 2026-11-07, as a default: a Ladybug transaction is the commit point and no separate effect log is kept. Ladybug kept committed rows and dropped uncommitted ones after SIGKILL; the log existed to make JSON file writes atomic. `docs/designs/storage.md`, section 2.3.)* The effect log is the commit point. Each write appends its effect to the project's log and syncs it before any file changes. After a crash, the functional map server replays the entries that the files do not yet hold.

**Status:** Proposed. The agent chose it at the founder's request ("please make recommendation"). The reasons are in `metaform/docs/designs/metaform-server-design.md`, Alternative G.

**R-4.6** This project's functional map server is built in Rust, as a library and a binary (`metaform/docs/designs/metaform-rust.md`). Ladybug leaves it. The Node server in `metaform/server/` is a test harness, built in minutes to test the contract. It is not the design and is never a source for it; the design is the founder's documentation set (the founder, when it was built: "this better not become the design we have one already").

**Status:** Proposed. It follows the founder's statement "at present we are working on the mcp server which exists in node". The chassis is event driven, in Rust, and uses Bevy (D-9). **Reconsidered 2026-11-07:** the founder: "I'm not against realizing metaform in rust also for this project". **Decided 2026-11-07: Rust** for this project's functional map server. The founder: "I recommend rust too"; "I dont mind creating a version of metaform in rust, in node, in python, thats fine.. it might be interesting to use in rust for this project". Other implementations may exist beside it; each must meet this specification. The Node server in `metaform/server/` was a quick first build and has no concurrency. **Decided 2026-11-09:** Metaform ships in three forms, Rust, Node and Python, and each stores its data as a structure of arrays (SoA): one narrow table per field or layer, keyed by element, not one record per element holding every field (AoS). **Reason:** "AoS gets slow fast" (owner, 2026-11-09). **Engines, decided 2026-11-09:** Rust keeps LadybugDB (R-4.1, R-4.16), with its write queue engine (R-4.7) handling multiple writers; Node and Python use SQLite, which both have built in. **Reason:** "its like the state of the art modern version, while the others are fine also.. but for certain projects ladybug useful" (owner, 2026-11-09). Ladybug stores each property as its own column, so its tables are SoA. Layer data is kept apart from the element's JSON column, as one Record node per layer item: built 2026-11-09 in `28d19ed` (R-4.16). The Node and Python forms and their SQLite store are designed in `metaform/docs/designs/sqlite-forms.md` and built in `metaform/node` and `metaform/python`. `metaform/conformance` holds the recorded cases that all three forms must answer in the same way.

## 5. The form

### 5.1 The tool

**R-5.1** The form is one MCP tool, `project-map`. Its input schema is in `metaform/mcp-tools.proposed.json`. Its commands are `add`, `update`, `delete`, `orphaned`, `search`, `layer`, `goto`, `map`, an addressed read and a raw dump. A key without a period is a command. A key that starts with a period is a raw dump (R-5.34). Any other key with a period is an addressed read (owner, 2026-11-09).

**Status:** Decided. **Source:** the founder's tool design; `metaform/docs/mcp-query-source.md`; `metaform/tool-examples.json`. The name: "something an agent can actually reason against is highly preferred over something they have no idea what it is for"; "dash if its allowed". The contract is named `project-map`; it has no `search` or `layer` until the build adds them.

**R-5.26** Tools are organized by module. A module exposes a tool, and all tools that act on the same functionality collapse into one tool. Tools are not gated by where an agent stands. A new module can also unlock commands and features under other tools that do not come from that module directly.

**Status:** Decided. **Source:** "the tools arent gates by locality they are organized my the module, a module exposes a tool, any and all tools that interact with the same functionaliuty should collapse hopefully into a single tool". Unlocking: "a new module can unlock commands and features under other tools that dont come from that module directly".

**R-5.2** Addresses on the form have no project name.

**R-5.3** The server knows which agent is calling, and that gives the agent's project. No command selects a project.

**Status:** Decided. **Source:** "the mcp server has a way to identify which agent is which". Until agent identity exists, each forwarder names its project folder when it connects (R-4.5), and the functional map server routes the agent's calls to that project. The folder is not part of the form.

### 5.2 Commands

**R-5.4** The form takes what the agent means, and the code does the work behind it. A write creates every path it needs, including the element that a want names.

**R-5.5** `add` keeps what is there: arrays grow, and other values are written. `update` writes to a path. `null` removes a field.

**R-5.35** A successful write answers `{"status": "ok"}` and nothing more. It does not repeat the command. A refusal repeats the command (R-5.24), so the agent sees what was refused beside the reason.

**Status:** Engineering decision, 2026-11-09; not an owner decision. Built. No owner document gives the form of a successful answer; the build repeated the whole command. **Reason:** the agent sent the command and has it. In four recorded intakes, the repeat was 29% of all bytes the tool delivered: 302,384 bytes fell to 215,946 on the same commands (`metaform/conformance/replay.py`). **When the other form is better:** if a write ever alters what was sent in a way the agent must see, the answer should carry that difference, not the whole command.

**R-5.38** The server publishes to agents the one command shape, with each part described once (`mcp-tool.published.json`), not the contract's schema, which restates that shape for each verb. The contract (`mcp-tools.proposed.json`) is unchanged and still checks every command.

**Status:** Built 2026-11-10 in the Rust, Node and Python forms, on the owner's instruction: "its too much if it the Ai isnt using the tool its describing"; "its one command... and one simple schema"; "thats the tooling and you can edit that to make it more efficient". The compact `tools/list` result went from 11,973 to 3,929 bytes on 2026-11-10, and to 656 bytes on 2026-11-11, when the published schema became the list of operations only, on the owner's statement: "I designed the tool surface to be well under 1kb not 12.. but with a list of operations". The published schema holds no description; the tool's own description is the contract's text. A check (`tests/check_published_schema.py`) shows it accepts every command of the conformance suite that the contract accepts.

**R-5.39** `help` is a read that answers one level at a time, and has three forms. `{"help": {}}` returns the schema of the `help` command itself, under the key `help`: one property, `help`, whose value is one of the command names `add`, `update`, `delete`, `orphaned`, `goto`, `map`, `addressed read`, `raw dump` and `help`. `{"help": "<command name>"}` returns `{"help": {"<command name>": <entry>}}`, where the entry is the contract's own (`mcp-tools.proposed.json`): the entry of the input schema's top-level `oneOf` that is the form for that command, with no `$defs`. `{"help": "<definition>"}` returns `{"help": {"<definition>": <definition>}}` for a key of the contract's `$defs`. A `$ref` inside an answer stays as the contract holds it; it names the definition an agent can ask for next. A command name comes before a definition of the same name. `help` reads nothing from the map and writes nothing. Any other value is refused with `FIELD_MISMATCH` and the remediation `{"help": {}}`.

**Status:** Built 2026-11-11 in the Rust, Node and Python forms, on the owner's instruction: "cant we add help onto the command surface to provide it also"; "The help command provides a schema showing they can request help to get the schema of any other command." **Reason for one level at a time:** the owner's rule of progressive discovery for this tool, "no information is presented in advance of it being needed, and especially not showing anything that isn't needed". An agent that needs one part of a command asks for that part and receives no other. The contract's `help` form takes `{}` or any text that is not empty; the list of command names is in the answer to `{"help": {}}` only.

**R-5.36** A deletion leaves no empty element. A write creates the element a want names (R-5.4). When the last want that names it is removed, and it has no fields, no wants and nothing beneath it, it is removed too, with each branch above it that is left the same way.

**Status:** Engineering decision, 2026-11-09. Built. **Reason:** a test intake left empty addresses in the map after it deleted the elements that named them, and `map` then listed addresses that hold nothing.

**Status of R-5.4 and R-5.5:** Decided and built. **Source:** "its a form with mechanics behind it where we do all of the heavy lifting in the code"; "it blocked because your logic doesnt allow the procedure by creating the database paths automatically which it absolutely should be".

**R-5.6** A want needs all of its fields.

**R-5.7** `delete` refuses an element that something still wants. The refusal returns a remediation command.

**R-5.8** A failed command changes nothing.

**Status of R-5.6 to R-5.8:** Proposed and built. The documentation set names the refusal in R-5.7 `DEPENDENCY_LOCK`.

### 5.3 Reads

**R-5.9** The address `.` means the root of the agent's project.

**Status:** Decided and built. **Source:** the founder's documentation set, module 5.2.

**R-5.10** A read of an address returns that element's own fields, keyed by its address: the form in which data is entered. Its wants come back only when the read names them. A read does not return who or what relies on the address, the attached layers, skills or memories; that takes `goto` (R-5.30).

**Status:** Decided. Not built. Replaces the rule "a read of an address returns one localized object" with skills, attached layers and the addresses on both sides. That rule had replaced "a read returns the address and everything beneath it", which was built. **Source:** "I was completely wrong when I said viewing an address shows its edges, you can view the wants and specify to view the wants like address wants, what you wont do is get the full breakdown of who or what relies on the address, or the wants and the attached layers that requires using goto". Earlier source, now replaced: "reading an address gives you that address in the map and its layers, and then names the attaches addresses". Naming wants in a read: `{"<address>": {"wants": {}}}` (R-6.27, owner, 2026-11-09).

**R-5.30** `goto` places the agent at an address. It returns what is directly linked there: the element and its wants, the full breakdown of who or what relies on the address (`wanted_by`, each with its want), the names of the attached layers, the frontmatter of the skills at that address when it has any, and the memory count. The agent's presence at that address decides which memory graph the memory tool shows (R-5.29). The server notes that presence after each `goto`, and that is how it knows which skills to present (owner, 2026-11-09). It returns nothing from the layers of other addresses. Knowledge arrives as a summary sheet: one JSON document shaped to describe the node and show where its data lives, with record counts, not records. Skills are in the MCP server, and nothing gates triggering one; an agent learns that a skill at a functionality exists only from the frontmatter `goto` delivers there. The root's skills are the base skills: an agent learns them when it joins the server, not through `goto` (owner, 2026-11-09; delivery at joining is not built). `goto` delivers this once per context: the first arrival delivers it, and a later arrival in the same context delivers only what has changed. Arriving at an address is also how an agent reads its inbox (R-6.23).

**Status:** Decided. Built 2026-11-07: `metaform-core` builds the summary sheet, and `metaform-server` delivers it once per connection; the form stays Proposed, so the founder can still change it. **Source:** "project-map needs a goto command"; "when you use goto, thats what triggers showing the frontmatter for the skills, showing the memory count and all of that stuff"; "an agent sees a memory count when viewing a element directly, but must use the memory tool to access them"; "goto only dumps new info IF the info changes its once per context! so first arrival, from there if you move between nodes you will not get that dump a second time in the same context, that is also how you get to read the inbox is by arriving at the address". Tracking delivery by part, and one connection counting as one context until the ACP handoff exists, are Proposed. A client can reset an agent's context while the connection stays open, so `goto` names the parts it holds back in `unchanged`, and a goto at a layer's definition element always carries that layer's `guidance`. The first delivery of a layer's instructions ends with the sentence that says where to read them again (owner, 2026-11-09: options A and B; built on branch `discovery-reset`). *(Changed 2026-11-09, engineering decision after four test intakes: `goto` at an ordinary element no longer carries a layer's rules. Its `instructions` part holds one sentence for each layer, "The rules for writing <layer> are at <definition address>. Read them only when you write <layer>." The rules are delivered at the definition element, as `guidance`. Reason: the rules, about 2,200 characters for the specification layer, reached every test agent on its first `goto`, before it could use them, and three of the four never wrote the layer. The same commands delivered 206,858 bytes in place of 215,946. This is progressive delivery: the agent is told the rules exist and where, and reads them when its work needs them.)* The form `{"goto": "<address>"}`, including each dependent's want in the breakdown, and holding presence on the connection until agent identity exists are Proposed, in `metaform/docs/designs/metaform-server-design.md`. Presence is state between calls, so it is held against the agent as R-8.2 allows; until identity exists (D-8), the connection stands for the agent. Summary sheet and skills: "the layer structure can carry other data but the system prescribes the minimal dump that arrives when you reach a functionality.. the knowledge gets dumped as a summary sheet, that means record counts not records"; "our skills will be in the mcp server...nothing stops you from triggering a skill, nothing gates triggering a skill, but agents dont get the context to know the skill exists until its relevent". The sheet's key names and reading a skill through the MCP resource template `skill://{name}` are Proposed.

**R-5.11** `{"map": {}}` returns the shallow graph of the whole project, `upstream`, `downstream` and `layer` included: the element addresses and the wants between them as edges. It carries no fields and no layers, except a mark on the one Definitive element. *(Changed 2026-11-09: this was the read of `.`, which is now the raw dump, R-5.34. The owner: "flat element names without any layers just call it map.. its the shallow graph shape".)*

**Status:** Decided. Replaces "a read of `.` includes `upstream` and `downstream` elements" with every intake field, which is built. **Source:** "if you read the root of the map you only get the connections tree, no layers not even the wants layer but you do get the relations as edges"; "you can ONLY get detail by reading an actual address"; "you can label the definitive functionality.. that we can give"; the reason: "that conveys understanding which helps reason on what the project itself is".

**R-5.27** `search` reads all content of the map, layers included, and returns where each match is, not its content. A match in a layer reads `Found: "code.bar.foo" in "baz" layer`. The functional map server walks every trunk-to-leaf path of the hierarchy, not only the flat list of addresses.

**Status:** Decided. Not built. **Source:** "I would let search match anything in the map not just addresses.. treat it like a deep search.. and the running process needs to enumerate all of the trunk to leaf paths via the hierachy"; the result form as the founder wrote it. The match rule, the limit of 50 results and the search of active layers only are Proposed, in `metaform/docs/designs/metaform-server-design.md`.

**R-5.12** The tool schema's address pattern must accept `.`.

**Status:** Built.

**R-5.21** A read returns only the fields named in `intake` (R-6.15). Other layers come back only when the read names them.

**R-5.22** A read with no command names what it wants. *(Changed 2026-11-09: the root dictionary `layers` and its read `{".": {"layers": {}}}` are superseded. Layers are defined as elements beneath the `layer` root scope (R-6.24). The owner: "we changes it it was never updated".)*

**Status of R-5.21 and R-5.22:** Decided. Not built. **Source:** the founder's documentation set, module 5.2; "There should be a way to ask. You just leave the command off". The example `{".": {"layers": []}}` is replaced. Listing layers is decision D-18 (R-6.24).

**R-5.23** `{"orphaned": {}}` returns a bare dictionary keyed by address: each orphaned element's address maps to its values. *(Changed 2026-11-07 from "a bare array": the founder: "anything with a unique key by name is a dictionary not an array".)*

**Status:** Decided. Not built. **Source:** "bare array because its a query.. by returning it as an array or as a dictionary its dishonest and misleading".

**R-5.24** Every refusal returns the command it refused, `"status": "error"`, a fixed error `code`, a `message` that says in plain words which rule the command broke, the `tested_sentence` where one applies, and the `remediation` command that fixes it, in that order. The rule each code stands for is documentation; it is not a field of the response. The codes are `TECHNICAL_NAME_ALIGNMENT_FAILURE`, `CANONICAL_NAME_COLLISION_FAILURE`, `ROLE_TAXONOMY_FAILURE`, `GRAMMAR_CONSTRAINT_VIOLATION`, `LAYER_NOT_REGISTERED` and `DEPENDENCY_LOCK`.

**Status:** Decided. Not built. **Source:** the founder's documentation set, module 6, and `intake_roles.md`; "input validationb is real and it must return why it was rejected". The functional map server adds codes in the same pattern: `NAME_ROUND_TRIP_FAILURE`, `PROJECT_NOT_REGISTERED`, `VERSION_MISMATCH`, `NOT_FOUND`, `ELEMENTS_BENEATH`, `WANT_INCOMPLETE`, `PROJECT_FAILED`, `NOT_PRESENT` and `INTERNAL_ERROR`. **Status of the added codes:** Proposed, in `metaform/docs/designs/metaform-server-design.md`.

*(Changed 2026-11-09 on the founder's direction.)* The response shape follows the founder's examples (`~/brain/mcp_query.md`, `intake_roles.md`, documentation set module 6); the build had sent a `rule` field and named `message` `reason`. `GRAMMAR_CONSTRAINT_VIOLATION` means only the module 6.4 check on `why` and `how`, which is not built (D-14). Failures that the build had sent under that code now have codes that name the problem: `FIELD_MISMATCH` (the command or an element does not match its schema), `ROOT_SCOPE_NOT_ALLOWED` (R-3.3) and `FIELD_ELEMENT_COLLISION` (one word used as both a field and an element beneath it). **Source:** the founder: "wouldnt that be a field mismatch or something that is a clear error message?" (2026-11-09). Built on branch `store-failure-error-structure`.

A remediation never removes or alters what the refused command did not address. The refusal of a second Definitive element gives the new element another role; it does not remove the role of the element that is Definitive already. **Status:** Engineering decision, 2026-11-09, built: a test intake received `{"update": {"<the Definitive element>": {"role": null}}}` as the remediation, and an agent that followed it would have removed the one element that says what the project is.

Every message for a command that does not have the right shape is written by hand (`metaform-core/src/shape.rs`), in a fixed order of checks, and names a place the way an agent writes it. No message comes from a schema validator. **Status:** Engineering decision, 2026-11-09, built. **Reason:** the validator's messages held Rust type names and JSON pointer paths, some pointed at the wrong problem, and they could not be equal in three forms.

A written `role` must be one of the four roles, spelled exactly (R-3.13); the refusal is `ROLE_TAXONOMY_FAILURE`. A stored map with older role names still loads and accepts unrelated writes. **Status:** built 2026-11-09.

**R-5.25** An element is deleted in four steps: the direct delete is refused, the remediation removes the want, an orphan scan confirms nothing wants the element, and the delete succeeds.

**Status:** Decided. **Source:** the founder's documentation set, module 5.3.

*(Superseded in part 2026-11-09: there is no `layers` dictionary. A layer is defined by an element beneath the `layer` root scope (R-6.24). How a layer is added and listed under R-6.24 is decision D-18.)*

**R-5.28** `layer` adds a layer by registering it in the `layers` dictionary (R-6.15). Its definition must have a schema, a `description`, a sentence (`template`) and an `instruction`. The schema is `fields`, in the form the wants definition uses (R-6.17): each field gives its `part_of_speech`, `rule` and `example`. Every other command works the same way, and a layer's data is written with them, like any other field. `layer` with nothing lists the layers: the names in the `layers` dictionary only, not their contents, as a dictionary. `layer` with a layer name returns that layer's contents. `layer` cannot add, list or return a layer in `intake` or `system` (R-6.15). A layer's definition says whether its records are named: a named layer's data at an element is a dictionary keyed by record name, and other layers' data is a list.

**Status:** Decided. Not built. **Listing source:** "to list layers just use the layer command and send nothing, but it only lists the layers in the layers key, and the names only not its contents to list its contents send layer plus the layer name". Reading "contents" as the layer's entry in the `layers` dictionary, not its data across the map, is the agent's reading. **List form source:** "layers are a dictionary with curley braces". **Data shape source:** "at the object it depends on the layers purpose, and the layers definition can control that"; "if the layer is named, then its a dictionary, otherwise they are a list with a incrementing key or something". The key `named` in the definition is Proposed. **Source:** "make a command called layer to add a layer. every other command works the same way"; "layer command must name its fields and sentence and instruction just like wants"; "layer needs a schema, description a template, and an instruction". Reading "schema" as the `fields` key that wants uses is the agent's reading. The form `{"layer": {"<name>": {<definition>}}}`, a second `layer` for the same name replacing the definition, and the storage of a registered layer's field in that layer's files are Proposed, in `metaform/docs/designs/metaform-server-design.md`.

**R-5.29** Memory is a module. It exposes its own tool for memories, which the functional map server brokers (R-5.13, R-5.26). The tool exists for context management: it keeps durable facts about the project at the addresses they come from. Its commands are identical to the modelcontextprotocol.io memory server's, and no command says where a memory goes. The tool shows a different memory graph depending on where the agent is, so the only way to read and write an address's memories is presence at that address (R-5.30). A memory can link to any address or any memory, so it can bridge two addresses.

**Status:** Decided. Not built. **Source:** "memories have an origination address, you can make a dedicated memory tool"; "make memories a module"; "they can name any address or memory to link to"; "you dont specify where you want to assign memories the memory command is identical to the canonical memory command, the difference is that it shows a differeent memory graph depending where ytou are.. that means the only way to read and write those memories is via presence at that address". Replaces "only the must name an address". The tool name `project-memory`, reading an address from a relation's `to`, and how memories are stored and removed are Proposed, in `metaform/docs/designs/metaform-server-design.md`.

**R-5.37** When a client connects, the server's `instructions` tell the agent where a person can see the map: the command `metaform gui`, and the address it prints, `http://127.0.0.1:4170/` unless that port is in use. The agent is told to give the user that address when it finishes an intake or changes the map for a user. The graph workspace shows its own address, with a control that copies it.

**Status:** Decided, owner, 2026-11-09: the address is shown in the workspace, and the instructions tell the agent to tell the user. Built. The wording, the port 4170 and placing the text in the MCP `instructions` field are engineering decisions. **Reason for a fixed port:** an address that changes at each start cannot be told in advance.

**R-5.31** A ticket selects an agent's context. A ticket ties the work to the functionality it concerns, so an agent does not need to travel the map to reach its context. Taking a ticket does for the agent what `goto` does for an address: it pre-orients the agent with the whole view of everything it needs for the task, organized in sections by what it is working on, like a file folder handed over at the start of a job. What does not concern the task is not shown, not even as an option. An agent in the project can accept a ticket, or be spawned to work on one. The skills at a functionality are written by the facilitation agent: when a ticket for that functionality is assigned on the kanban board, it makes sure the skill layer holds a skill for the work. `goto` never creates a skill. It delivers only the frontmatter of the skills that already exist at the address and at the root (R-5.30), so an agent sees the skills for the place where it works, not every skill in the project, and reads in full only the one its task needs.

**Status:** Decided. Not built. **Source:** "we have two maps.. one map is a map of context, you dont need to travel to reach context, tickets can select your context by tieing the functionality to the ticket, you take the ticket, it does for the agent essentially what goto does. an agent in the project, can accept a ticket or get spawned to work on a ticket, this gives the system the ability to pre-orient the agent, it hands the agent the 360 degree view of everything they need for what they are tasked with.. if you are working on the computer network you dont need the plumbers skills or their wrench. you dont need to see the options as even being options. its like walking into the job and being handed a file folder all divided into sections, and organized related to what you are working on in the project". How tickets are stored, which tool carries them, and the folder's sections are not yet decided. The facilitation agent and skill scoping: owner, 2026-11-09. Reason: frontmatter scoped to the place keeps the agent's context tight even when many skills exist there. The facilitation agent is not a base mechanism of Metaform and is not built.

**R-5.32** Focused context reaches an agent in two ways. Push: when an agent arrives at an address (R-5.30) or takes a ticket (R-5.31), the functional map server announces the skills for that position on the agent's `subscriptions/listen` stream, as `notifications/resources/list_changed`, or as `notifications/resources/updated` for a skill the agent already subscribed to. Pull: the result of `goto` carries each skill's `skill://` URI, and the agent reads it with `resources/read`. Pull always works; push works when the agent's client has opened a subscription. Skills are served as SEP-2640 skills; a skill generated for a ticket and a position is marked `"resources": "dynamic"`.

**Status:** Proposed by the founder for push with a fallback: the founder's draft Metaform skill (`metaform/agents/metaform-skill.md`, 2026-11-07) has the agent use the skills pushed after `goto`, and otherwise read the skill URI. The founder: "this is OUR features we are referring to and how we deliver focused context". The protocol mapping is Proposed. **Reason:** SEP-2575 defines `subscriptions/listen` with `resourcesListChanged` and `resourceSubscriptions` (specification 2026-07-28, "Subscriptions"). SEP-2640 requires a host to load a skill given only its URI, and allows a server not to list every skill, so skills can stay out of the startup listing and appear only where they apply.

**R-5.33** Intake and layer work run as MCP tasks. The server pushes each task's status through `notifications/tasks` to clients that listen for its task ID, so an orchestrator never polls.

**Status:** Proposed. **Reason:** the founder pointed to SEP-2663, the tasks extension (2026-11-07). An intake run is long work, and `DECISIONS.md` rules out recurring polling.

**R-5.34** A key that starts with a period is a raw dump: the stored nested JSON at that path. The path is the JSON path `$.<project>.<address>` with `$.<project>` left off. `{".": {}}` dumps the whole project, and `{".code.server": {}}` dumps that element and everything beneath it. Every layer is included, `wants`, `skills` and `memory` too, because each is a layer. Names are in the agent's form (R-4.11).

**Status:** Decided, owner, 2026-11-09. Built on branch `specification-store-batch`, not merged. **Reason:** a read without the period answers in the form data is entered (R-5.10); a read with the period answers in the stored form, so both forms can be read. **Source:** "period should dump the full nested json because thats what makes sense"; "can we have starts with a . is a raw dump, and how it is now dump how it reads now"; "without the . it matches how data is entered"; "Memory is a layer you can dump it"; "skills is a layer". Keying the result by the path asked for is Proposed.

### 5.4 The functional map server and the CLI

**R-5.13** The functional map server is a broker to modules.

**R-5.14** Every MCP tool can be used through the CLI, so a harness without MCP access can still use it.

**R-5.15** A CLI command is not exposed as an MCP tool by default. No rule requires parity. Tools stay dense: one tool carries many commands.

**R-5.16** The CLI is hierarchical. Each module owns a branch of the command tree, and each level shows only what is available at that level.

**R-5.17** Every CLI command can be run as one complete command line, so an agent does not need an interactive session.

**Status of R-5.13:** Decided by R-2.9: "the mcp server needs to be able to broker for the other parts of the system".

**Status of R-5.14 to R-5.16:** Proposed by the founder, not yet confirmed. **Source:** "mcp tools can be used via the cli ... but not vice versa"; "at the cli modules must be hierarchial". On what lands in MCP: "MCP is for data manipulation and reading data. cli commands dont go into mcp.. so an export command would be cli" (2026-11-06). Exporting a specification (R-1.2) is a CLI command.

**Status of R-5.17:** Proposed.

### 5.5 The tool and the prompt

**R-5.18** The tool reads data, writes data and keeps the data correct. An order of steps lives in a prompt, not in the tool.

**R-5.19** Intake has no start and no stop. Its data lives in one place and is visualized.

**Status of R-5.18 and R-5.19:** Proposed. **Source:** "you are building way too much code here.. too much ceremony.. my vision is that its a tool the ceremony live in a prompt"; "there is no start and stop there is a place where data lives and its visualized". Both quotes were relayed by the agent working on `RchGrav/metaform-archive` (then named `RchGrav/metaform`). The wording is an agent's. The earlier build's `intake_start`, `intake_finish`, locks and verification passes are that agent's examples of what to exclude. The founder has not reviewed that list.

**R-5.20** Logic is added to a tool only to fix an observed issue.

**Status:** Decided. **Source:** "logic should not be added just to be added it has to fix an observed issue."

## 6. Layers

**R-6.28** A layer is called an overlay.

**Status:** Decided by the owner, 2026-11-11. Not applied: this section, the procedure, the schema, the tool contract, the `layer` root, the `layers` and `blocked_layers` arrays and the pages still say layer. **Source:** "I have a better name for layer. call it an overlay". The two arrays on an element are `overlays` and `masked_overlays`, in place of `layers` and `blocked_layers`. **Decided by the owner, 2026-11-11. Source:** "or overlays and masked_overlays"; "in a real physical sense if you have info in an overlay the way to remove it from just a small region is to mask it". **Reason:** an array names what is written at the element, an overlay laid on or masked there. Whether an overlay is active at an element is the result of the project's list, the placement and the masks, so "active" and "inactive" stay words for that result and are not array names. The root `overlay` in place of `layer`, and "overlay" in place of "knowledge layer" in prose, follow from the name and are the agent's reading until the owner confirms them.

### 6.0 What a layer is

**R-6.0** A layer is one kind of knowledge, spread across the map and placed only where it applies. An address holds a piece of a layer only if that kind of knowledge applies to its functionality. Delivery gives an agent exactly the knowledge its work needs, nothing more and nothing less.

**Status:** Decided. **Source:** "a layer is the same type or kind of knowledge spread across the map specifically where it applies"; "ideally it should always strive to nothing more and nothing less than exactly what is neede".

**R-6.21** The map indexes the layers, and each layer is kept in its own files. A layer can be many files, such as one file for each address. The functional map server can own and control layers, and parts outside it can add layers through it.

**Status:** Decided. **Source:** "a layer is indexed by the map as a separate file"; "a layer could be many files if its an address inbox it would be this_address_inbox.json or some similar naming scheme"; "it can own and control layers conceivably but those layers must be able to be added externally". Outside parts go through the functional map server because it is the only writer (R-4.4).

**Proposed for the founder (2026-11-07):** keep each layer and each piece as a separately indexed record, but group the pieces physically in the map's database instead of loose files. An inbox file for every address would put tens of thousands of files on disk. Options and the recommendation are in `docs/designs/storage.md`, section 4. Until the founder answers, the build uses grouped records.

**R-6.22** Wants is a layer, and it is included in intake. `goto`, or an address read that names wants, returns them (R-5.10, R-5.30). `map` shows wants only as edges (R-5.11). `intake` is a reserved group: a layer in it is not listed with the project's layers, and the layer itself cannot be deleted. Agents still write and remove its data at an address.

**Status:** Decided. **Source:** "wants is a layer that is included in intake!"; "wants is a layer but its in a reserved group called intake which keeps it from appearing under layers or being accessible to delete"; "agents can assign data to these layers at the address they just have no control over the existence of these layers".

**R-6.23** The address inbox is a layer whose content lasts only until it is delivered to whoever works at that address next. It is not part of the base intake system and comes later.

**Status:** Decided. Not built. **Source:** "an inbox at an address is like what a knowledge layer is but it its life span is only until its delivered to whomever works there next"; "inbox isnt part of the base intake system, it comes later".

### 6.0.1 Layers defined in the map, and the specification layer

**R-6.24** Every layer works the same way. A layer is defined by an element beneath the `layer` root scope that has an `instruction` field. The layer's field name at receiving elements is the definition's last address segment, and its value there is a list of records. No two definitions share a last segment. The specification layer is defined by `layer.document.specification`, so its field is `specification`. The server writes that definition into each main map and refuses any other write to it.

**Status:** Decided, owner, 2026-11-09, relayed by Jorge, the store agent: layers have no mechanism of their own, the specification layer is listed as `layer.document.specification` in the main map, and its data is a JSON field named `specification` on the receiving elements. The reason for the `layer` root is in R-3.3: definitions under a project root would read as part of the project. It replaces the `layers` dictionary of R-6.15 and R-5.22 (owner, 2026-11-09). Built on branch `specification-layer-core`, not merged. Built 2026-11-09 (branch `layer-and-remediation-fixes`): a write that puts a list at an element under a name that is neither a defined layer nor a system layer (`skills`, `memory`, `sources`, R-6.15) is refused with `LAYER_NOT_REGISTERED`. Only lists the write changes are checked. An intake test on axum found the tool accepting such a list. A definition element with an `instruction` field, the last segment as the field name, and locking the code-defined definition are Proposed, in `metaform/docs/designs/specification-layer.md`. Moving the `system` layers of R-6.15 into the map is not decided.

**The whole of a layer, owner, 2026-11-09.** A layer definition is a schema object. It is the complete input validation for one array name, and that array can then be written at any address. All of a layer's arrays have the same name. A layer that is not wanted is not returned: the reads leave out the arrays with that name. Nothing more is needed to make a layer or to leave one out. **Reason:** agents kept adding machinery to layers, and the design is this small on purpose. **Consequence for D-18, engineering decision, not an owner decision:** a layer is made with `add` at its `layer` address, like any other element, and removed with `delete`. No `layer` command is needed (R-5.28). **Reason:** the definition is an object in the map, so the commands that write the map already write it, and one form for every write is the project's rule.

**Where a layer is active, owner, 2026-11-09.** This confirms the layer list and the walk (R-6.1 to R-6.9) and settles where each part is kept. Not built.

1. *Defined.* The definition under `layer` creates the layer. Creating it does not turn it on.
2. *Enabled.* The core database, which tracks the projects, lists the layers that are enabled for a project. The filter is kept there. A layer that is not listed is off everywhere.
3. *Linked.* A layer is linked to an element by naming it in that element's `layers` array. An enabled layer is active at the element it is linked to and at everything beneath it, down to the leaves. A layer never flows toward the trunk.
4. *Blocked.* A block at an element keeps the layer from flowing further down. By default every element allows every layer, as a mask with every layer set (R-6.6).
5. *Moved.* To make a layer active nearer the trunk, the link is moved to an element nearer the trunk.

**Reason:** a layer is placed only where it applies (R-6.0), and one link at the right element covers everything beneath it. **Closes D-13:** the names in an element's `layers` array are the names of definitions under `layer`. **R-6.9:** the list of enabled layers is stored in the core database and written on the form at `.` (below). **The form of a block, owner, 2026-11-09:** an element blocks a layer by naming it in its `blocked_layers` array. This replaces `-name` inside the `layers` array (R-6.4, R-6.9). To block a layer at one element only, name it in that element's `blocked_layers` and name it again in the `layers` array of the elements directly beneath, where it is linked again and flows on to the leaves. **Reason:** linking and blocking are two lists of plain names, so no name carries a sign and each array has one meaning.

**The same layer in both arrays, owner, 2026-11-09:** a write that would leave one layer named in both `layers` and `blocked_layers` at one element is refused. This replaces the last sentence of R-6.6 ("the addition wins"). The likely case is an agent that adds a block at an element where the layer is linked. The refusal has the form of every other refusal (R-5.24). Its message says only that the block cannot be made until the layer is unlinked, in the wording of the delete refusal (R-5.7). Its remediation removes the link, which does what the agent meant to do. The message does not mention the root's `layers` array: the remediation already serves the intent, and more words would cost the agent reasoning. **Reason:** the write contradicts the element's state, so the system cannot know which the agent meant, and a silent rule would hide the mistake. The code name `LAYER_LINK_CONFLICT` and the exact message are Proposed. The remediation uses `delete` with the array item named, the form that removes a want (R-5.25), because the form has no `remove` command:

```json
{
  "add": {"code.engine.game": {"blocked_layers": ["porting"]}},
  "status": "error",
  "code": "LAYER_LINK_CONFLICT",
  "message": "cannot block, 'porting', must be unlinked first",
  "remediation": {"delete": {"code.engine.game": {"layers": ["porting"]}}}
}
```

**The root's `layers` array.** The list of enabled layers (state 2 above) is read and written on the form as the `layers` array at `.`, as R-6.9 first said, and it is stored in the core database. Removing a layer from that array turns it off for the whole project and leaves every link and every record in place.

**R-6.25** A definition may declare the format `markdown_blocks`. Its records are blocks of prose: `{"level": 1-4, "title": "...", "text": "..."}` with an optional `code`, and the first block may be `{"text": "..."}` alone, as an intro. The tool enforces the heading structure, so the prose can be exported as Markdown and imported again without loss: the first titled block is level 1, each level is at most one more than the level before it, no level is above 4, and text holds no Markdown heading line outside fenced code. A code is a key that other text can cite. It is unique in its layer across the map, ignoring case. The tool refuses nothing else about the text. The TASTE targets are reported by the export's check.

**Status:** Decided, owner, 2026-11-09: the specification layer encodes Markdown heading levels for its text so that it round-trips, and the tool enforces them; its text is not normative and follows TASTE. Block codes that are unique across the specification, like a key: owner, 2026-11-09, relayed by Jorge, the store agent. The reason: the skeleton holds functionality only (R-3.20), so a specification's prose needs a place in the map that agents can maintain and export. The block shape, the level limit of 4, the code form and refusing only structural problems are Proposed, in `metaform/docs/designs/specification-layer.md`.

**R-6.26** Layer records are accepted only at an element that intake has placed in the skeleton, meaning one with `technical_name`, `name` and `role`, and at the root once the map has a Definitive element. Elements in the `layer` scope hold no records.

**Status:** Decided, owner, 2026-11-09: the specification layer starts after the intake step. Reading "after intake" as this test on each element is Proposed, because intake has no start or stop to mark (R-5.19).

**R-6.27** `goto` lists every defined layer whose records are allowed at the address, with its record count, and delivers each layer's guidance once per context. A read names a layer in the slot where it is written, with `{}` as its value, and returns its records: `{"<address>": {"specification": {}}}`, `{"<address>": {"wants": {}}}`.

**Status:** Decided, owner, 2026-11-09: agents use the MCP server to keep specifications up to date. The `instructions` field of the `goto` result is Proposed. The read form is Decided, owner, 2026-11-09: every layer is named in a read where it is written, because that is consistent with the other commands. **Source:** "its consistent with the rest thats key"; "as soon as you see it anything else seems wrong"; "anything else is a deviation.. this works like everything else, less tools.. better design". The read form changes the protected tool contract on the owner's instruction.

**R-6.28** `metaform specification export` prints the map and its specification layer as one Markdown document. The export can be imported again: a heading for each element names its address, block levels are relative to that heading, and a stale document is refused on import. `--check` reports the TASTE targets without failing.

**Status:** Decided, owner, 2026-11-09: a CLI export produces a well-organized specification document. The layout, the import and the check rules are Proposed, built by Ida on branch `specification-layer`.

### 6.1 The layer list

**R-6.1** A project has one layer list. The list enumerates the project's layers.

**R-6.2** The layer list controls which layer names are visible.

**R-6.3** The list is transitive to the leaf: every element beneath the project root inherits it.

**R-6.4** Any element can add a layer. Any element can negate a layer with `-`. The change applies to that element and to everything beneath it.

**R-6.5** `upstream` and `downstream` are outside the tree. They do not inherit the project's list.

**Status:** Decided. **Source:** "layer names visible are controlled by an active layer list... we enumerate the layers"; "layer list is at the project level and its transitive you can add it to any element and negate a layer also"; "-is fine.. then its transitive to the leaf; upstream and downstream are outside of the tree".

### 6.2 The walk

**R-6.6** The active layers at an address come from a walk from the root to that address. At each step:

```text
outgoing = (incoming & mask) | select
```

Negations apply first. Additions apply second. If one element adds and negates the same layer, the addition wins.

**R-6.7** The intake layer is the metaform itself. It is not selectable.

**Status:** Decided. **Source:** `reference/theory/technical-reference.md` section 9; earlier implementation `src/metaform/data/selection.py` in `RchGrav/metaform-archive`.

**R-6.8** A hidden layer is removed after the walk, with every layer built from it. A layer that is still being built is not selected.

**Status:** Proposed for adoption from the same sources.

### 6.3 The form of a layer change

**R-6.9** The project list is written at `.`, and a change is written at the element:

```json
{"update": {"code.engine.game": {"layers": ["-porting", "rust"]}}}
```

**Status:** Proposed. The founder accepted `-`. How a list of names relates to the `layers` dictionary of R-6.15 is decision D-13.

**R-6.10** A layer name that is not on the project list is refused, unless it is a tag.

**R-6.11** Working agents can read active layers. Only Systems can change them. This cannot be enforced until agent identity exists.

**Status of R-6.10 and R-6.11:** Decided. **Source:** the founder confirmed the design list and said "yes".

**R-6.12** A layer declaration holds its `variable`, fields, sources, tags, producer, and whether it is mutable and hideable.

**Status:** Superseded by R-6.16.

**R-6.13** `investigations` and `couplings` are not layers.

**Status:** Decided. **Source:** "those arent approved and the names are terrible". Their content is ephemeral (R-3.16).

### 6.4 Root registries

**R-6.14** The root registries limit what a dump of `.` returns, which layers can be created, and which arrays come back when a read includes a layer.

**Status:** Decided. **Source:** "the intent is to limit what is dumped when you dump . to limit what layers are permitted to be created, and what arrays to dump when you dump the details of a layer or specify the inclusion of a layer".

**R-6.15** Three dictionaries define a project's fields and layers. `intake` and `system` are reserved groups. They are global data, shared by every project, and are not kept in a project's own data. A layer in `system` is created only by editing the code. Agents write data to `intake` and `system` layers at an address, but have no control over whether those layers exist. `layers` is kept in the project's own data.

- `intake`: the fields of the base map, keyed by field name. A key's presence puts the field in the base view. Its value holds the field's definition, which may be empty.
- `system`: capabilities shared across projects: `skills`, `memory` and `sources`. They are system layers. `skills` are skill entries as SEP-2640 defines them. `memory` is an array of memories at the address, like every layer's data (owner, 2026-11-09: "memories needs to be an array"; "memory is a countable singular noun", so the name stays `memory`). Together they form a graph of durable, atomic facts about the project, adapted from the MCP sample memory server, which agents keep relevant through create, read, update and delete. Memory is a unique layer: its shape is a graph, and a new memory extends it by naming existing memories. It works like the modelcontextprotocol.io memory server. Each address has its own memory graph, read and written only by an agent present at that address. A memory can link to any address or any memory. Memory is read and written through its own module's tool (R-5.29).
- `layers`: the project's own layers. A layer must be registered here, with the `layer` command (R-5.28), before data is written to it. *(Superseded 2026-11-09 by R-6.24: there is no `layers` dictionary. A project's layers are defined as elements beneath the `layer` root scope.)*

```json
{".": {
  "intake": {"technical_name": {}, "name": {}, "role": {}, "uri": {}, "status": {}, "wants": {}},
  "system": {"skills": {}, "memory": {}, "sources": {}},
  "layers": {}
}}
```

**R-6.16** A definition may hold `description`, `ref`, `prompt`, `instruction`, `fields`, `template` and `artifacts`. `fields` gives each field's `part_of_speech`, `rule` and `example`. `template` is a sentence whose placeholders are filled from the data. The sentence must read correctly, and it formats the readable report.

**R-6.17** The `wants` definition:

```json
"wants": {
  "template": "{this.address} ({this.name}) requires {other.address} ({other.name}) in order to {why}, which {how}.",
  "fields": {
    "why": {"part_of_speech": "Bare infinitive verb phrase", "rule": "State the active goal as a sentence fragment beginning with a base action verb. Do not include a leading 'to', subject nouns, or any words ending in -ing.", "example": "drain raw frames from the network interface card"},
    "how": {"part_of_speech": "Third-person singular present indicative verb phrase", "rule": "State how the provider satisfies the goal beginning with a present-tense verb ending in -s or -es that agrees with 'which'. Do not include subject nouns, 'by', or any words ending in -ing.", "example": "holds descriptor pointers across contiguous memory segments"},
    "direction": {"part_of_speech": "Controlled value", "rule": "One of inbound, outbound or two-way, relative to the element that holds the want.", "example": "inbound"}
  }
}
```

**R-6.18** A prompted layer is created in this order: infer the layer from its prompt, define it beneath the `layer` root scope (R-6.24; changed 2026-11-09 from "register it in `layers`"), then run the prompt against the addressed elements. A plugin layer links a plugin's artifacts to the functionality they refer to. Its `instruction` is delivered once when the plugin is triggered through ACP while the layer is active.

**R-6.20** When a definition has a `template`, a dump renders the data as the readable report, one sentence for each record.

**Status of R-6.15 to R-6.18 and R-6.20:** Decided. Not built. **Source:** the founder's documentation set, modules 4 and 7. Where the groups live replaces "the project root holds three dictionaries": "there is also system layers like skills and memory system layers can only be manually created by editing the code"; "intake and system should be in the projects global data not in the projects own db". Memory: "memory is a unique layer because its a graph shape that gets extended, by naming existing memories"; "memory works like the modelcontextprotocol.io memory server only the must name an address", since replaced by presence (R-5.29); "they can name any address or memory to link to". How memory is stored and removed is Proposed, in `metaform/docs/designs/metaform-server-design.md`. Holding the global data in one file in the server's code is Proposed, in `metaform/docs/designs/metaform-server-design.md`.

**R-6.19** A `features` layer tags every element with the feature or features it belongs to.

**Status:** Decided. Not built as a prompted layer. **Source:** "We need to create a feature knowledge layer, that can be just an instruction to tag every element with what feature or features they belong to".

## 7. Links between projects

**R-7.1** An `upstream` element can link to another project through `uri`. The value can be `file://`, `https://`, a relative path such as `../project`, or a home path such as `~/project`.

**R-7.2** The `uri` is where an agent goes to perform intake on that project.

**R-7.3** A want stays local. It points at a local `upstream` element.

**Status:** Decided. **Source:** "when an element begins with upstream its actually possible to have a "uri": "file:// or https:// or just a relative path"; "the uri is where an agent would go to perform intake on a project".

## 8. Protocol

**R-8.1** The target is MCP `2026-07-28`. Under R-4.5, the functional map server serves MCP on each forwarder's connection, over a Unix socket in the home. The Rust server does this with rmcp on `<home>/server.sock`; it negotiates `2026-07-28` and answers older clients too (tested). (The Node harness used the SDK's `serveStdio`, which negotiated that version in a test.) **Status of the socket:** Proposed; built on that default.

**R-8.2** The server keeps no session state. Anything an agent needs between calls is carried in the request or held by the server against the agent's identity.

**Status:** Proposed. MCP sessions are removed in `2026-07-28`, so this follows from the protocol. The state held against the agent's identity lives in the agents module (section 11; the founder: "thats where the session state has to live"). Until it exists, the functional map server holds presence and `goto` delivery against the connection (R-5.30).

## 9. Build order and acceptance

**Status:** Proposed. The order follows `metaform/docs/designs/metaform-server-design.md`. It replaces the earlier chassis-first order, which an agent wrote.

Build in this order. Each step ends with its tests passing. The test budget is five per feature, through the public interface.

1. Names and refusals: R-4.11, R-5.1, R-5.24.
2. The Ladybug store, the write manager, and layers: R-4.1, R-4.3, R-4.7, R-4.8, R-4.16, R-5.28, R-6.15, R-6.22 (`docs/designs/storage.md`). *(Corrected 2026-11-07: this step said "the JSON store, the SQLite log"; JSON map storage was never decided.)*
3. The functional map server, the forwarder, the CLI and routing: R-4.4, R-4.5, R-5.3, R-8.1.
4. Reads, `goto` and search: R-5.10, R-5.11, R-5.30, R-5.21, R-5.22, R-5.27. Then the memory module: R-5.29.
5. Announcements and the viewer: R-4.10.

The layer list and the walk, R-6.1 to R-6.8, are built after decisions D-7 and D-13. The specification and founder-boundary edits listed before as step 6 are made.

No data is migrated. Existing maps are cleared and rebuilt by test intakes with `metaform/Intake.md` 3.1.

A step is accepted when:

- the client negotiates `2026-07-28`;
- `{".": {}}` returns the connected index for the whole project, including `upstream` and `downstream`, with no detail beyond the Definitive mark;
- a field that is in no group and is not a registered layer is refused;
- once R-6.1 to R-6.8 are built: a layer on the list reaches every leaf beneath the root, and does not reach `upstream` or `downstream`; an element can negate a layer, and a child can add it back without changing its siblings;
- export equals the imported document, apart from D-4.

## 10. Open decisions

| ID | Decision | Blocks |
|---|---|---|
| D-1 | Closed by R-3.4: the want fields are `why` and `how`. The intake procedure still says `goal` and `function`. | Nothing. |
| D-2 | Closed by R-3.6: the values are `inbound`, `outbound` and `two-way`. | Nothing. |
| D-3 | Closed by R-3.13. | Nothing. |
| D-4 | The shape of `wants` in the document: the schema's array, or the canonical map's object. | Exact export equality. |
| D-5 | How an agent looks inside an `upstream` project that has had an intake. Proposed: the address continues past the link, as `upstream.service.billing.code.api`. The owner's example of a link between projects puts a root scope directly after the prefix, as `upstream.code.engine.physics` (R-3.3, 2026-11-09). | Section 7 read path. |
| D-6 | How the store matches a `uri` to a project, including `~` on a shared server and the same repository reached by `file://` and `https://`. | Section 7 read path. |
| D-7 | Whether a read returns only active layers, or whether a raw read exists. | Step 4. |
| D-8 | Which identity the server trusts. MCP client names are self-reported. | R-5.3, R-6.11. |
| D-9 | Closed for the language: the chassis is event driven, written in Rust, and uses Bevy (founder, 2026-11-03: "I would like to see the chassis be event driven, be in rust and use bevy"). Still open: how modules connect to the chassis. | The chassis and its hook into the functional map server (R-2.9, R-2.11). |
| D-11 | Whether `collection` stays a root scope. The procedure lists seven root scopes, and the documentation set lists six. Owner statement, 2026-11-09: a project has four root types, two more roots hold what is outside the project, and `layer` exists to define the layers. Answered the same day: intake has six roots, and `collection` is not one (see the correction after R-3.3). Not applied yet: R-3.3's text, the protected intake procedure, `names.rs` and `roundtable/metaform.json` (which has `collection.workspace.shared`) still have `collection`. The owner's reason is not recorded yet, and the procedure needs the owner's direct instruction. | R-3.3. |
| D-12 | How a project with more than one metaform is stored. The earlier specification kept one store per metaform. | R-4.1. |
| D-13 | How a layer change at an element (R-6.9) relates to the layer definitions beneath the `layer` root scope (R-6.24). The `layers` dictionary it first named is superseded. Closed 2026-11-09: an element's `layers` array names definitions under `layer` (see "Where a layer is active", after R-6.24). | Nothing. |
| D-19 | Whether `name` may equal `technical_name` when the project has no name of its own for the element. R-3.12 says the two differ. The intake procedure allows the standard term. Enforcing R-3.12 made four test agents invent names (R-3.12, 2026-11-09). Options: (a) keep the procedure's rule and reword R-3.12 to "differ when the project has its own name"; (b) keep R-3.12 and change the procedure to say what `name` holds when the project has none, such as leaving `name` out. Recommended: (a), because it needs no change to the protected procedure and an invented name is worse than a repeated one. | R-3.12. |
| D-18 | How a layer is added and listed now that definitions are elements beneath `layer` (R-6.24): the `layer` command of R-5.28, or `add` at a `layer` address. | R-5.28. |
| D-14 | How the grammar check tells a verb ending in `-ing` from a noun such as `ring` or `string`. The documentation set forbids words ending in `-ing` in `why` and `how`. | R-5.24. |
| D-16 | How chaining (R-4.15) relates to links between projects (section 7). Partly answered 2026-11-09: an outside project is one `upstream` or `downstream` element in the map, with a `uri` naming its repository; its own functional map is a separate map with its own addresses, read only on request (R-4.15). Storage of a chained map is a default: a `Map` node in its parent's database, reached by `CHAINS`, promotable to its own database (`docs/designs/storage.md` 2.2). The earlier recommendation of a folder with its own `map.json` is withdrawn. | Section 7 read path. |
| D-17 | Defaults taken 2026-11-07 (`docs/designs/storage.md` 2.3, 2.4): the layout under the home, maps grouped into project databases, no separate effect log, at most 16 open databases (lowered from 64 after measuring memory, storage note risk 5) with a 64 MB pool, a 16 GB limit and 4 worker threads each. Open only for the founder's confirmation of the grouping (R-4.1). | Nothing; the build proceeds on the defaults. |
| D-10 | How the system scales sideways. Default for the rule (`docs/designs/storage.md` 2.5): every store has one owning process, declared in settings and proved by a lock file; every other process, on this machine or another, goes through that owning process, never through a shared file. Still open: how several world servers or chassis divide work. | Any multi-chassis deployment. |

## 11. Not in this document yet

These exist in other sources. They enter this document when the founder settles them.

- The intake procedure. The working source is `intake-new.md` in the founder's folder, and the project copy is `metaform/Intake.md`. `metaform/Intake.xml` is the older project prompt.
- The founder's documentation set, copied unchanged into the project as `metaform/docs/documentation-set.md` (from the founder's `Universal Intake & Layer Architecture Documentation Set.md`, 2026-11-02; SHA-256 `89a545b433e7da46`). Its decisions are in this document. `intake_roles.md` and `roles.md` stay in the founder's folder until the founder asks for them. Its full examples and error payloads stay there.
- The context resolver, Composer, Facilitator and ACP harness in `TOPOGEE.md`.
- Mutation: the four families in `specs/authority/mutation_framework.md` in `RchGrav/tempo`.
- The three topologies and the common navigation interface.
- Chassis, modules, settings and languages.
- Collaboration: multi-agent roundtables. The founder wants a roundtable module again, wired to Jev, so that agents given a goal can hash it out together ("something really cool happens when you set a goal, and then put a bunch of agents together and let them hash it out"). In the earlier system, Jev is the decision service at `code.service.decision` (`metaform/metaform-canonical.json`), and past roundtables are summarized in `docs/roundtables/`. The earlier roundtables module is at `/home/rich/metaform-tasks/src/metaform/modules/roundtables` (about 7,900 lines of Python, with a second engine under `roundtable/`); another session reported that its turn order, PASS rounds, ranking and handoff are process held in code, which R-5.18 would move to a prompt. How a roundtable runs and shows when a project has no map is not decided yet. In metaform the stage is drawn as a mode of the 3D map (`modules/web/page/app/roundtable/stage.js:176`), so a table there needs an intake first. It may land in the Bevy work rather than here ("maybe that doesnt land here and it lands in bevy"). Work on it starts once the infrastructure is up ("we will be able to break ground on it and start thinking about it once we get infrastructure up and going"). Proposed by the founder on 2026-11-06: an agent builds its own metaform map to describe whatever it intends to build, and owns that map. It can bring other agents into a roundtable to refine the design. The map's owner is the roundtable's head, and can end the table when it has the answers it wanted ("allow ... agents to build their own metaform map to describe whatever it is they intend to build and give them ownership of their own metaform, then they can employ other agents into a roundtable to work with them and help refine the design. making the metaform owner the roundtable head, and giving them the control to end the table when they feel they got the answers they wanted").
- The agents module. The founder will specify it after the functional map server is built ("after we build the mcp server we can spec the agents module"). The founder's intent so far:
  - It is in charge of ACP, agent names and messaging. Messaging is the inbox feature.
  - Messaging is under the `agent` tool: `inbox`, `message` and `interrupt` are commands under `agent`, as in `agent message` ("messaging is under the agents command like agent message with message being the command under agent"). A message waits until the receiving agent is complete ("inbox works like when you send a message to an agent waits until they are complete").
  - An interrupt is like a message but does not wait: "much ruder, agents wont like you if you do it but sometimes it is necessary". The example: an agent learns of a change order from the user and interrupts the other agents with a message.
  - The user can also message agents through the GUI.
  - Because the module runs every harness the same way, it gives one search across harnesses. The search covers the ACP logs: all agent-to-agent and user-to-agent communication. Every agent has equal access to it.
  - Status of what follows on waking, profiles, accolades and scoring: illustrations of what ACP makes possible, not requirements ("right now these details dont matter to the specs, its just illustrating some of the ways acp can be used in interesting ways"). The founder leaves the method to the agent that specifies the module ("it might be even more interesting to let you choose how that works"; "when it comes to that I'll let you decide").
  - Every agent gets a name ("all of the agents get cool names").
  - Session state lives in the agents module, held against the agent's identity ("thats where the session state has to live"). The functional map server's presence and `goto` delivery move there from the connection.
  - An agent's identity is born out of its first context ("agent identity is born out of their first context, you can look at metaform"). `TOPOGEE.md` section 5 names the agent from a hash of its initial context. Places to look in the earlier system: `reference/architecture/chassis-modules.md:807` (sessions keep their ID, name and history) and `reference/corrected-handoff/01_specification/METAFORM_FUNCTIONAL_CORE_v0.4_CANDIDATE.md:108` (a retired context keeps its agent name and history).
  - The tool surface comes first: what lives under one `agent` tool, in line with one tool with many functions ("consider the tool surface itself and what might live under an agent command. This is inline with our approach of 1 tool many functions").
  - The module is about identity: creating an agent, waking a past agent by name (much like resume), and creating system agents ("think of the agents module being about identity, being able to create an agent, waking a past agent by name (much like resume), it also allows us to create system agents").
  - Example system agent: an identity agent that uses Haiku. It is called when an agent that existed in the past is woken by name. Waking first calls it to create or update the agent's profile and summarize its past context.
  - The profile is saved as `profiles/<agent name>.md` in the `agents` folder of the project's path under `~/.metaform`. Its maximum size is 2 KB. ACP prepends it to the agent's first message when the agent wakes, not in every context ("ACP prepends this to their first message, but its not repeated every context, just when it wakes up.. and its max size is 2KB").
  - The profile does not list the agent's commits, and the identity agent does not build that list: the system tracks commits itself ("commits list would be not part of their profile actually nor would haiku need to build that into the profile since the system itself could track that").
  - A woken agent can still search its past history.
  - An agent cannot view its score. It can view only its accolade ("An agent cant view its score it can only view its accolade"). The score is the peer rating kept across the agent's history (`reference/history/decision-log.md` D-46, on a 0–105% scale).
  - The accolades: Silver Rating at 80% or more, Gold at 90% or more, Platinum Honors at 100% or more. The founder first gave them chances of waking of 20%, 40% and 60%, then corrected the math: past agents go into a pool, each accolade is a relative weight, and the pool is weighed against spawning a fresh agent ("we need to put past agents in a pool, and use the odds as a relative weight, and in that scenario it needs to be weighted against spawning a new agent").
  - The founder's view of the trade: the cost is the compute Haiku spends to build the profile, and the benefit is a gamble on whether an agent that wakes with a sense of accolade and past accomplishment in the project does better work ("does an agent who wakes with a feeling of accolade and past accomplishment in a project affect its work").
  - Work is traced through logs: the system logs the tickets, who accepts each ticket, and who makes each commit ("we log the tickets and who accepts tickets and who makes commits"). Which past agents enter the pool for a new ticket is not decided.
  - An agent makes a commit, and can claim an unclaimed commit in the project if that commit was made in the past 30 minutes, so it cannot rack up past feature commits. A commit adds 5% to the agent's current session score. When an agent traces trouble to a commit, 5% is taken from the committing agent's average ("a commit grants 5% onto their current sessions score.. if an agent traces trouble to the commit it takes away 5% from your average"). `AGENTS.md` already has the trace: a feature that breaks after its commit gets a note in `docs/trouble-log.md` naming that commit.
  - To settle: how a session score enters the average of D-46, and whether the 105% ceiling of the earlier system still holds once commits add points.
  - To settle when the module is specified: the functional map server is the only process that writes under `~/.metaform` (R-4.4), so profiles are written either through the functional map server or under an exception the founder grants.
