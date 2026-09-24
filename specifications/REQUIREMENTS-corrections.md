# Proposed corrections to REQUIREMENTS.md

Each entry gives the requirement, the corrected text, and why. The why is part of the requirement: it is what lets a later reader keep the design when the wording is not enough. Requirements not listed stay as written. Nothing here is applied until Rich approves it. Entries marked **Question** need Rich's answer first.

## Header and section 1

**Header.** Status: product requirements drawn from Rich's design. Rich's design is the authority; where this file and the design differ, this file is corrected.
*Why:* the requirements were written from Rich's description of the design. A document that calls itself the complete, superseding contract is obeyed by every agent that reads it, so its errors spread unless the design stays above it.

**REQ-001.** These requirements are the product contract. Older documents, code and tests are evidence, not requirements.
*Why:* agents mine whatever they find for rules. One named contract stops old plans and accidental behavior from becoming requirements.

## Section 2: purpose and semantics

**REQ-013.** A namespace address names a Type and reads as its name. An element's identity in a project survives a change of its Type.
*Why:* the address says what kind of thing an element is; the element is this artifact's realization of it. A later intake or correction can type the same element better, and everything attached to that element, memory and layers alike, must follow it rather than be orphaned.

**REQ-015, added.** A join runs one way: the receiver owns it, and the provider serves it. A relationship in the other direction is its own join, with its own purpose and encounter function.
*Why:* each join is one receiver's why served by one provider's how. Two elements that need each other hold two different purposes, so they are two joins, and neither join is the other reversed. This keeps every join's meaning single and keeps the receiver, purpose and encounter structure acyclic.

**REQ-017, replaced.** Everything Metaform holds is a layer, the intake's map included. A layer carries one inferred variable, attached on an element, on a join, or on a new element and join that the layer creates. A layer declares its behavior: mutable or immutable, hideable, transitive.
*Why:* when every layer answers one question and attaches the same way, layers compose: any set of them can be selected together, and a module can add one without knowing about the others. That is what makes modules composable. Declaring behavior on the layer lets the engine apply revisions, visibility and propagation uniformly, so no module rebuilds those rules.

**REQ-018. Question.** This requirement says `asset` replaces `media` and adds an `entity` trunk. Canonical Intake 1.1 lists the roots as code, document, media, data and stakeholder. Which is current?

## Section 3: intake

**REQ-023, replaced.** Annealing keeps a combined element as a subtype inside the one join it shares with its parent, at the receiver end or the provider end. The subtype keeps its own address and its own purpose or encounter function. It is reachable only through that join, and layers attach to it directly.
*Why:* annealing keeps the root map minimal without discarding functionality. A subtype only exists because it shares that join with its parent, so it lives there. Kept inside the join, it can never become a root or an edge between elements; keeping its address and its own purpose or encounter lets memory and layers still reach the specific part.

**REQ-025.** Native and latent reasoning each produce their own layer, each with its own provenance record.
*Why:* the latent perspective is valuable because it differs from the native one. Separate layers keep the two perspectives from blending, and selecting both puts them side by side when a reader wants to compare.

## Section 4: chassis and modules

**REQ-031, corrected list.** Remove "assignment and nonce resolution" until nonces are designed. Replace "generic revision and provenance machinery" with "revisions for immutable layers and one provenance record per layer".
*Why:* the chassis holds only what every module needs now. Nonces come after the MVP, and provenance is kept per layer, so the chassis carries no machinery for either beyond that.

**REQ-035.** Modules load from the system place (shipped with Metaform), the user place (`modules/` in the Metaform home), and installed packages that declare a `metaform.modules` entry point.
*Why:* community extensibility means a module can be installed like any Python package; the entry point is the standard way a package announces itself. Keeping no module place inside project folders follows from all data being global.
**Question:** is a per-project module place still wanted, and if so, under that project's data in the home?

**REQ-201.** The template demonstrates the current contract: verbs with nouns and adverbs, sync and async operations, events, settings declared in code (including a select from the module's own data), MCP tools, and a caution verb that acts only with `--confirm`.
*Why:* authors copy the template, so it must show exactly what the chassis offers today and nothing it no longer does.

**REQ-202, replaced.** Ship one template module, in its own folder with a README and tests. It is the example authors copy and the module the chassis is developed against. Other modules are added only when a need exists.
*Why:* building many speculative modules is what repeatedly buried the chassis. One template that exercises every feature proves the chassis and teaches authors at the same time, and anything else earns its place by a real need.

## Section 6: settings

**REQ-060, added.** A module declares its settings in its own code through the settings module. That declaration is the whole of its settings work: one schema drives set, unset, validation, defaults, help and the settings screen.
*Why:* a module author writes settings once and never touches CLI or screen plumbing. One schema means the switches, the help and the screen cannot drift apart.

**REQ-062, added.** Out of the box, the defaults are the working settings. Metaform and every module work with zero configuration.
*Why:* low-friction onboarding. Settings exist to tune a working system, not to make it work.

**REQ-065, added.** `unset all` returns settings to their defaults and skips glued ones; `unset all --unglue` resets those too. A select setting can take its choices from a list in code or from the module's own data.
*Why:* glue lets a user keep a baseline through a reset. `all` is the noun the reset acts on; every switch names a setting, and there is no setting called all. A data-driven select lets a module, like the workflow module, offer choices it authored itself.

## Section 7: user interface

**REQ-071, added.** Commands are verbs, arguments are the nouns they act on, and switches are adverbs that change how a verb runs. `metaform` alone shows status. `metaform help` is a brief overview. `metaform help <thing>` is the man page; `<thing> --help` and `-h` give its syntax. `help commands` and `help switches` are the indexes. Every error names one next command.
*Why:* a consistent grammar makes every command predictable. The two kinds of help serve two needs, understanding and typing, and merging them fails both. A brief overview keeps the first screen readable. An error that names the next command keeps an agent on the surface instead of sending it into the source, where it starts guessing at the design.

**REQ-074, replaced.** The working context is made of ordinary settings, per folder: the project (defaulting to the registered project that contains the folder), the workflow, and the command surface. A `set` that narrows the surface says so and gives the exact way back, `metaform abort <workflow> --confirm`. Commands outside the surface are not shown and do not run, on the CLI or over MCP. `unset all` returns the folder to its own safe default.
*Why:* context as settings needs no extra machinery and is visible and reversible like any setting. Removing commands from the surface holds even for agents running with full permissions, where harness permissions do not. The orchestrator that narrowed the surface holds the exact way back and acts with confidence; a subagent meets only the caution and hesitates. The wording steers, and nothing gates inference.

**REQ-075. Deferred.** Assignment context is designed together with nonces, after the MVP.
*Why:* the MVP delivers a working CLI and MCP first; assignment context depends on the nonce design.

## Section 8: work identity and MCP

**REQ-080 to 085. Deferred.** The MVP has no nonces. The nonce is designed later as the handle that carries a job's text to a worker exactly as written.
*Why:* the nonce's purpose is repeatable prompt chains across agents and harnesses, without the orchestrator rewording the work. That is valuable but not needed to make the map, layers and MCP work, so it waits.

**REQ-083, replaced.** The Metaform home keeps a working-folder table. Nothing is written into a project folder to mark it.
*Why:* agents run in many folders, including worktrees. The home knows every folder's context without leaving files that pollute repositories or get picked up by build tooling.

**REQ-086.** The MCP server serves the full tool set of the folder's command surface. Each module verb is a tool built from the same declaration as its CLI command. Harness tool permissions narrow it further where they are used.
*Why:* one declaration for both surfaces means MCP and CLI can never disagree, and an agent without MCP loses nothing. The command surface setting governs what exists, so the narrowing holds even when a harness grants everything.

## Section 10: data and provenance

**REQ-101 to 105, replaced by one requirement.** Provenance is one record per layer, showing exactly how the layer was created: the module and the workflow within it, the prompt, the model, the role, and whether it was blinded. Nothing is recorded per item or per read.
*Why:* provenance tracks what a feature of the system actually uses and nothing more. Knowing how a layer was made, by which perspective, under which role, is what lets layers be trusted, compared and reproduced. Per-item and per-read records turn provenance into bloat, and bloat defeats a system whose purpose is to give agents only what matters.

**REQ-106.** An immutable layer changes only by a correction, recorded as a new revision; earlier revisions stay readable. A mutable layer, such as memory, changes in place.
*Why:* the map is the shared foundation, so a change to it must be explicit and traceable. Memory is the fast, local fix that agents keep current as they work, and in-place change is what keeps it cheap.

**REQ-108.** All Metaform data is global, under the Metaform home. Nothing is written into a project's folder.
*Why:* every agent, in any folder or worktree, reaches the same data. No project carries copies that go stale or get mistaken for source.

**New.** Storage gives direct indexed access to every element, join, subtype and layer item. A whole layer, or every layer at one element or join, is one direct read. No read scans every record to find one.
*Why:* agents navigate by meaning, one question at a time: who receives this, why, how, what do other layers say here. Each question must be answered by going straight to the answer, so the structure does the orienting and the agent keeps its inference for the task.

## Section 11: knowledge and memory

**REQ-124. Question.** This requires hiding to follow dependencies item by item. With provenance kept per layer, should hiding follow dependencies between layers, so a layer built from a hidden layer is hidden too?

**REQ-125. Replaced.** Covered by the per-layer provenance record.
*Why:* how knowledge was generated is exactly what the layer's provenance records.

**REQ-126, added.** Memory follows the interface of the MCP reference memory server: open nodes, search, create, add observations, relate, delete. Its nodes are the map's elements and joins.
*Why:* agents already know that interface. Attaching memory to the map's own nodes means a single memory at a node corrects a wrong inference right where agents read it, so the map does not have to be perfect to be useful.

**REQ-127, replaced.** Memory is mutable in place and carries no provenance.
*Why:* memory is agents' working notes. Its value is being cheap to add and fix; history and provenance would make every note heavy.

## Section 16: compatibility

**REQ-180, added.** Before 1.0 the contract changes freely. From 1.0 on, a module declares the lowest chassis version it needs and checks for capabilities rather than versions. Breaks come only in a major release. A frozen suite of earlier modules enforces this.
*Why:* community modules must keep working across chassis updates, or nobody builds on the chassis. Checking capabilities lets a module use new features where they exist without breaking on older chassis. Until the first release the design is still settling, so compatibility machinery would only slow it.

## Section 20: remediation instructions

**Question: remove.** It instructs agents to remediate from the September conformance audit and the remediation matrix.
*Why:* that process belongs to the old build, not to the product. Left in, it directs every new agent back to the old plan.
