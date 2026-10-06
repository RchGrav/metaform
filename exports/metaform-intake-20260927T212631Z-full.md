# Full export of intake intake-20260927T212631Z-45108a

Project metaform, metaform `main`, layer `intake-20260927T212631Z-45108a`, created 2026-09-27T21:26:31Z, finished 2026-09-27T21:51:37Z.
Provenance: module intake, workflow canonical-intake, model opus

63 elements, 41 joins, 29 subtype joins, 273 refs, 19 work records. Every field is printed as stored, nothing shortened. The agent's report and feedback are in the two files beside this one.

## module author

- Address: `stakeholder.author.module`
- Role: VE
- name_length: 2

### module author receives from plugin system

- Receiver: `stakeholder.author.module`
- Provider: `code.system.plugin`
- Type: purpose
- Name: common base
- Purpose: Add a capability to Metaform as a module of its own, declared once, that behaves like every built-in module on the command line and over MCP and keeps working as the chassis changes.
- Function: Takes one MODULE = Module(...) declaration of verbs with their nouns and switches, subscriptions, start, stop and a status hook, and builds from it the command, its help page, its MCP tool and its settings, handing every call a Context with its folder, project and store.
- EF: Encounter
- Relation: declares a module once in its own folder and receives its command, help page, tool and settings from that one declaration
- Verb: declares
- Observation: module.py's Module, Verb, Noun, Subscription, Status and Context, BASE-035. An author copies src/metaform/modules/template, sets MODULE.id to the folder name, writes a purpose of two to four sentences ending with metaform help <id>, and runs metaform enable <id>. A module can also live in <home>/modules or ship as a package with a metaform.modules entry point. Before 1.0 the contract changes freely and the template's CHANGELOG.md records each change; REQUIRES_CHASSIS and capability checks come at 1.0, BASE-020.
- Non-goal: It does not let one module import another; modules cooperate through events.
- Ref path: src/metaform/module.py
- Ref path: src/metaform/modules/template
- Ref spec: BASE-035
- Ref spec: BASE-019

#### Subtype: module contract

- Provider: `code.contract.module`
- Name: module contract
- Function: States what a module must provide before the chassis loads it: SUPPORTED_OS as a literal, a MODULE whose id equals its folder or entry point name and whose purpose is not empty, verb names that make valid tool names, and nouns typed str, int, bool or json, only the last of them many.
- EF: Function
- Relation: states what a module must declare before the chassis will load it
- Verb: states
- Observation: module.py and loader._import. A verb's run and a subscriber may be a function or a coroutine and run the same way, BASE-009; a Stop carries one next step; a caution verb acts only with --confirm; surfaces=('cli',) keeps a verb off MCP, as approve and mcp serve are.
- Ref path: src/metaform/module.py
- Ref spec: BASE-015
- Ref spec: BASE-035

#### Subtype: module template

- Provider: `code.template.module`
- Name: template
- Function: Gives a new module every file and declaration the example has, empty: README.md with the headings BASE-034 asks for, CHANGELOG.md recording each contract change, its own tests folder and a CI workflow for Linux, macOS and Windows.
- EF: Function
- Relation: gives a new module every file and declaration it needs, empty and ready to copy
- Verb: gives
- Observation: src/metaform/modules/template ships disabled and loads with no verbs; its CHANGELOG lists 0.2.0, 0.3.0 and Unreleased, the last adding work records and the map.changed topic. QUAL-016 makes every capability added for a feature update it.
- Ref path: src/metaform/modules/template
- Ref spec: BASE-019
- Ref spec: QUAL-016

#### Subtype: example module

- Provider: `code.module.example`
- Name: helloworld
- Function: Shows each contract feature working once: greet with a noun, a switch and a published event, an async wait, a history kept as a layer through the store, a caution verb, a work record and its resolution, a verb for one system, settings with a select drawn from its own data, and a status line.
- EF: Function
- Relation: shows each feature of the contract working once, each with a test that fails if the chassis drops it
- Verb: shows
- Observation: src/metaform/modules/helloworld ships disabled; its greetings are items of the layer helloworld.greetings on the element code.module.helloworld, and a greeting appears live in the web GUI through map.changed without any code for it. beep runs on Windows only.
- Ref path: src/metaform/modules/helloworld/__init__.py
- Ref path: src/metaform/modules/helloworld/tests/test_helloworld.py

#### Subtype: extension guide

- Provider: `document.guide.extension`
- Name: Extending Metaform
- Function: Walks a module author from the running example to a copied template, the declaration, the per-call Context, declared settings, the graph and knowledge facilities, events and async work, lifecycle, and packaging into a wheel.
- EF: Function
- Relation: walks a module author from the running example to a packaged module of their own
- Verb: walks
- Observation: docs/guides/extending-metaform.md, 243 lines, and each module's README.md.
- Ref path: docs/guides/extending-metaform.md

## agent host

- Address: `stakeholder.host.agent`
- Role: VE
- name_length: 2

### agent host receives from mcp server

- Receiver: `stakeholder.host.agent`
- Provider: `code.server.mcp`
- Type: purpose
- Name: MCP server
- Purpose: Start Metaform in an environment of its own, the same way on every system, and give the agents it runs every Metaform capability as tools, with the instructions for using them.
- Function: Speaks MCP over stdio through the official SDK's low-level server, listing on each request one tool per verb on the folder's command surface, plus set, feedback, list_reports and read_report, and the history, prompt and clear tools while the chassis is on the surface; each call runs with its own Context and returns the verb's result as the command line shows it.
- EF: Encounter
- Relation: launches metaform mcp serve through uvx and lists the tools and instructions of the folder it started in
- Verb: launches
- Observation: modules/mcp declares DEPENDENCIES mcp>=2.2, so the SDK and its compiled parts stay out of the chassis, BASE-026; serve is a command-line transport verb and never a tool. A coroutine verb is awaited in the server's loop so the host's cancellation reaches it; a plain verb runs in a worker thread. Every tool takes an optional project and layers for one call; every error ends with one Next line; after each call the server fires map.changed for what changed. How the server finds the project when a host starts it outside every project folder is open, MCP-011; PROJ-005 falls back to the set tool.
- Non-goal: It serves one host over stdio on this machine; remote hosting comes later, and no tool takes a nonce.
- Ref path: src/metaform/modules/mcp/server.py
- Ref spec: MCP-002
- Ref spec: MCP-004
- Ref spec: MCP-025

### agent host receives from installer

- Receiver: `stakeholder.host.agent`
- Provider: `code.installer`
- Type: purpose
- Name: metaform install
- Purpose: Be set up once to start Metaform's server and load its skill, with every change to its configuration previewed and backed up, proven to work, and removable without losing any entry of its own.
- Function: Checks the system, Python and uv first, previews every file it will change with its backup, registers the uvx entry through each tool's own command or by merging its JSON config, copies the one fixed skill into each tool's skill folder, proves each registration starts a server that lists tools, and on uninstall removes only Metaform's own entries and files.
- EF: Function
- Relation: registers Metaform's server with each chosen tool, copies the skill, and proves the registered command starts a working server
- Verb: registers
- Observation: install.py. claude, codex, gemini, cursor and vscode are set up; copilot, factory, antigravity and claude-desktop are detected and listed as unverified, not offered, E2. Without a terminal and without tool names nothing changes; naming tools or all sets up without asking. Backups go to ~/.metaform/backups/install/<UTC time>/; the installs table keeps what was set up, so a second run adds no duplicate. Each tool's own command has two minutes. A JSON config that is not an object holding mcpServers is left unchanged and the install stops, naming it.
- Non-goal: It installs no software itself, not even uv, and writes nothing into a project folder.
- Ref path: src/metaform/install.py
- Ref spec: MCP-013
- Ref spec: MCP-016
- Ref spec: MCP-020

#### Subtype: probe client

- Provider: `code.client.probe`
- Name: proof
- Function: Starts the exact registered command from the user's home, writes initialize, notifications/initialized and tools/list as newline-delimited JSON-RPC, and passes the tool only when both answers come back with at least one tool within 30 seconds.
- EF: Function
- Relation: starts the registered command and passes it only when it answers initialize and lists at least one tool
- Verb: starts
- Observation: probe.py uses the standard library only, since the chassis does not depend on the mcp SDK, BASE-026; protocol version 2025-06-18. A server request is answered with error -32601, a notification is ignored, and any line on standard output that is not JSON fails the proof, MCP-017.
- Ref path: src/metaform/probe.py
- Ref spec: MCP-017

#### Subtype: agent skill

- Provider: `document.skill.agent`
- Name: skill
- Function: Tells an agent in any tool that Metaform holds the project's functional map, and to run metaform in the project's folder and metaform help agents, or read the MCP server's instructions, for the live state and the next step.
- EF: Function
- Relation: tells an agent to ask Metaform itself for the live state and the next step
- Verb: tells
- Observation: src/metaform/skill/SKILL.md, one fixed text copied as real files, never symlinks, to ~/.metaform/skills/metaform, ~/.agents/skills/metaform and each chosen tool's skill folder. It carries no module text, so enabling a module changes no skill file, MCP-021.
- Ref path: src/metaform/skill/SKILL.md
- Ref spec: MCP-021

### agent host receives from package builder

- Receiver: `stakeholder.host.agent`
- Provider: `code.builder.package`
- Type: purpose
- Name: directly run wheel
- Purpose: Run a custom Metaform inside a code execution sandbox that has no network and nothing installed, without touching any Metaform installed beside it.
- Function: Carries every pure-Python dependency inside the wheel under metaform/_vendor, pinned with uv at build time, and a root __main__.py, so python <wheel> runs Metaform from the wheel with a home of its own; a compiled dependency stays in Requires-Dist only and the build names it with the module that needs it.
- EF: Encounter
- Relation: runs python on the wheel file and gets a working Metaform with a home of its own and no network needed
- Verb: runs
- Observation: The build needs uv and network or a warm uv cache; running the wheel directly needs neither when every carried dependency is pure Python, BASE-024. The wheel's home is ~/.metaform/wheels/<name>-<version>, never the main one, BASE-023; its data can later be pulled into the main home with metaform import wheel=<name>-<version>, each metaform arriving as its own.
- Non-goal: It never replaces, downgrades or changes an installed Metaform, its dependencies or its data.
- Ref spec: BASE-023
- Ref spec: BASE-024
- Ref spec: BASE-042

#### Subtype: bootstrap

- Provider: `code.bootstrap`
- Name: wheel bootstrap
- Function: Puts the wheel and its carried dependencies first on the import path, drops any other path that provides a metaform package, sets METAFORM_HOME to the wheel's own folder unless it is set and METAFORM_WHEEL to the wheel's path, then runs the command line and exits with its code.
- EF: Function
- Relation: puts the wheel first on the import path and gives it a home of its own before running Metaform
- Verb: puts
- Observation: The BOOTSTRAP text in build.py becomes the wheel's root __main__.py; nothing is unpacked to disk. The installer reads METAFORM_WHEEL to register the running wheel as its source, MCP-010.
- Ref path: src/metaform/build.py
- Ref spec: BASE-042

## agent orchestrator

- Address: `stakeholder.orchestrator.agent`
- Role: VE
- name_length: 2

### agent orchestrator receives from chassis

- Receiver: `stakeholder.orchestrator.agent`
- Provider: `code.chassis`
- Type: purpose
- Name: chassis
- Purpose: Start every agent it hands work to from the project's recorded functional map, what each part is for, who receives it, why and how, instead of having each agent rebuild that understanding from the files.
- Function: Keeps each registered project's Inference Metaform in the Metaform home, the intake map with its correction stack, knowledge layers and memory, and serves it through one command line and every module it loads, working on its own with every feature module disabled.
- EF: Function
- Relation: keeps the project's Inference Metaform in the home and serves it to every agent through its command line and the modules it loads
- Verb: keeps
- Observation: cli.py dispatches 21 chassis verbs and every module verb; home.py, data/ and loader.py hold the registered projects, one SQLite store per metaform and the modules. With every module disabled, status, help, settings, export, import and query still run, BASE-001. Nothing is written into the project folder; the home is ~/.metaform or METAFORM_HOME. The chassis starts no model and runs no workflow, BASE-003.
- Non-goal: It does not run agents, workflows or models; hosts start agents and the orchestrator hands them work by name.
- Ref path: src/metaform/cli.py
- Ref spec: BASE-001
- Ref spec: BASE-003

### agent orchestrator receives from settings system

- Receiver: `stakeholder.orchestrator.agent`
- Provider: `code.system.settings`
- Type: purpose
- Name: working context
- Purpose: Give each worker it starts a context of its own, the project, the commands it may run and the layers it sees, without hiding the orchestrator's own commands, and put it back in one step.
- Function: Holds the working context as ordinary folder settings, --project, --modules and --layers, which the orchestrator can store for another folder with folder=<path> before a worker starts there; a narrowed surface hides and blocks every other command on the command line and over MCP and prints the exact way back.
- EF: Encounter
- Relation: sets a worker's folder to its project, its commands and its layers before the worker starts, and unsets them to go back
- Verb: sets
- Observation: CLI-021, CLI-022 and PROJ-007: metaform set --modules workflow,memory folder=<path>. Narrowing never enables or disables a module. The fourth context setting, --workflow, belongs to the workflow module, which is not built. Settings live in the home keyed by folder, so a worker in a worktree anywhere finds its context by running metaform where it stands.
- Non-goal: It is not a permission system and holds no nonce; what an agent may do is the tools it is given.
- Ref spec: CLI-021
- Ref spec: CLI-022
- Ref spec: PROJ-007

### agent orchestrator receives from intake

- Receiver: `stakeholder.orchestrator.agent`
- Provider: `code.intake`
- Type: purpose
- Name: intake
- Purpose: Have a workpiece mapped by a subagent that reads the method from Metaform by name, word for word, so the map depends on the procedure and never on how the orchestrator reworded it.
- Function: Serves the Canonical Intake with only the project's target filled in and the recording lines appended, then records the map one element, join or subtype join per call into one building intake layer, lets the agent anneal, read it back one receiver at a time, correct it and finish it, and at the finish makes it the metaform every read sees.
- EF: Function
- Relation: serves the Canonical Intake by name and records the map one object per call into a building layer that no read sees until the finish
- Verb: serves
- Observation: modules/intake: prompt, start, element, join, subtype, absorb, show, edit, remove, finish and status, each also a tool intake_<verb>. Nothing recorded is refused for its content; what does not fit is stored as given and named in a notice, BASE-044. A record sent before start starts the intake; a second start resumes it; an intake into a metaform that already has one goes into a new metaform, activated at the finish. The status hook shows Intake: none yet with the notice to delegate the intake to a subagent. The tools carry no condition field; an object's condition is a work record written with map_work.
- Non-goal: It never starts a model, never parses an intake answer as XML, and never grades what it records.
- Ref path: src/metaform/modules/intake/__init__.py
- Ref spec: BASE-039
- Ref spec: MAP-040
- Ref spec: MCP-009

### agent orchestrator receives from map api

- Receiver: `stakeholder.orchestrator.agent`
- Provider: `code.api.map`
- Type: purpose
- Name: map module
- Purpose: Hand a worker one address and have it read, before it changes anything, what relies on that part, what that part relies on, and what the layers in context hold there, instead of reading the implementation to find its place.
- Function: Serves the store's reads and writes as verbs and tools: where returns an element with every join it provides and receives, the subtype joins inside them, its open work records and the layers at it; roots returns the map's entry, the vested entities and the defining element with their joins; the other reads return joins, identity, subtypes, layers, nodes, context, links, citations, history and search, each join with the layer it comes from.
- EF: Function
- Relation: returns, for one address, what relies on it, what it relies on and what the layers in context hold there
- Verb: returns
- Observation: modules/map declares 31 verbs, each calling exactly one store operation, served as map_<verb> tools; its only switch is --raw. where leaves ids and empty fields out unless full=true, so the read stays small. The module's purpose tells agents to start with map_where for an address and map_roots with none. Its writes are knowledge, work, select, mask, clear, hide, tag, answer and the metaform verbs; approve is declared for the command line only.
- Non-goal: It computes no visibility of its own; select, mask and hiding are applied inside the store's reads.
- Ref path: src/metaform/modules/map/__init__.py
- Ref spec: BASE-038
- Ref spec: STORE-025

### agent orchestrator receives from knowledge layer

- Receiver: `stakeholder.orchestrator.agent`
- Provider: `code.layer.knowledge`
- Type: purpose
- Name: knowledge layers
- Purpose: Give each job exactly the knowledge meant for it at each part of the map, practices, porting notes, specifications or anything a prompt asks for, without copying knowledge into the map or building a separate map per job.
- Function: Keeps each body of knowledge as its own layer answering one question, built object by object through the one tool map_knowledge, attached at elements and joins or at objects the layer creates and links to the map, marked ready when finished, and toggled on per folder by name or by tag.
- EF: Function
- Relation: keeps each body of knowledge as a layer answering one question, attached where it applies and toggled on for the jobs that need it
- Verb: keeps
- Observation: layering.py and the map module's knowledge verb, operations create, add-element, add-join, add-subtype, add-property, add-item, add-ref, add-plan, edit, remove, correct, finish, peel and discard. Every call names its layer; whoever has the tool may write any knowledge layer, before or after it is finished. A building layer is in no read in context. A knowledge layer's joins extend the map only while it is toggled on, and every read of a join names its layer. Each layer has one provenance record: module, workflow, prompt, model, role and blinded. Its objects are free of the functional map's naming rules, MAP-013.
- Non-goal: It never changes the intake map or a correction; only a correction layer changes the metaform.
- Ref path: src/metaform/data/layering.py
- Ref spec: LAYER-016
- Ref spec: LAYER-018
- Ref spec: LAYER-019

#### Subtype: layer selection

- Provider: `code.selection.layer`
- Name: select and mask
- Function: Resolves which layers reach each address: it starts from the folder's --layers toggles at the trunk, at each prefix toward the leaves removes the layers masked there and adds those selected there, then removes hidden layers and every layer built from a hidden one, and every read path uses that one resolution.
- EF: Function
- Relation: resolves the layers that reach each address from the trunk toward the leaves and applies that one answer on every read
- Verb: resolves
- Observation: selection.py's Resolver; select and mask rows live at type addresses, and a subtree's rows are read in one range. A join takes its receiver's selection and a subtype join its parent's receiver's. Building layers are never selected, and correction layers take no part: they always apply. A select or mask row whose layer is hidden or still building is reported as unresolved, never replaced by a default, STORE-035.
- Ref path: src/metaform/data/selection.py
- Ref spec: LAYER-007
- Ref spec: STORE-019

#### Subtype: transitive property

- Provider: `data.property.transitive`
- Name: properties
- Function: Attaches a property to one element; it applies at that address and at every address toward the leaves, and shows without applying at every address toward the trunk, so a language attached at the installer and another at the engine both show at code while neither reaches the other's branch.
- EF: Function
- Relation: applies from its element toward the leaves and shows toward the trunk
- Verb: applies
- Observation: STORE-039; the context read returns the applying and the visible sets apart. A property meant for a prefix with no element goes on an element the layer creates there, linked by the namespace tree and needing no join. Items and joins never travel; only properties do. The intake produces no properties; they come from knowledge layers, MAP-022.
- Ref spec: MAP-022
- Ref spec: LAYER-005
- Ref spec: STORE-039

### agent orchestrator receives from correction stack

- Receiver: `stakeholder.orchestrator.agent`
- Provider: `code.stack.correction`
- Type: purpose
- Name: correction layers
- Purpose: Fix what the map got wrong, move a join to the receiver it really serves, remove or add a part, explicitly and in order, so every agent stands on the same corrected map and every earlier version stays readable.
- Function: Applies each finished correction layer on top of the intake map in the order finished, as new versions of what it changes, moves, removes or adds; lets only the top layer be peeled off; keeps orphaned what a removal leaves with nothing to attach to; and marks every layer built on a corrected thing for re-examination.
- EF: Function
- Relation: applies each finished correction on top of the intake map in order and lets only the top one be peeled off
- Verb: applies
- Observation: corrections.py; written through map knowledge: op=create kind=correction, op=correct id= reason= with evidence=, remove=true, or receiver, provider or parent to move a join, then op=finish, and op=peel for the top layer. history shows a thing's intake version, then each correction's. An element's address never changes; its joins move instead. A correction layer is never toggled, masked or hidden, and never changes a knowledge layer's things. The web GUI removes the top layer after a warning read from peel_preview.
- Non-goal: It never rewrites a dependent layer; dependents are marked for re-examination and left as they were.
- Ref path: src/metaform/data/corrections.py
- Ref spec: LAYER-011
- Ref spec: STORE-017
- Ref spec: STORE-034

### agent orchestrator receives from agent memory

- Receiver: `stakeholder.orchestrator.agent`
- Provider: `code.memory.agent`
- Type: purpose
- Name: memory
- Purpose: Have a small wrong inference, or anything a later session must remember about a part, corrected or kept at the node where the next agent reads, so the map need not be perfect to be useful.
- Function: Offers the reference memory server's operations, create entities and relations, add and delete observations and relations, read the graph, search nodes and open nodes, over the map's own elements and joins, keeping each observation and relation as one item of a mutable memory layer any agent may read and change in place.
- EF: Encounter
- Relation: adds an observation at the node it concerns, and the next agent that opens that node reads it there
- Verb: adds
- Observation: modules/memory, nine verbs served as memory_<verb>. The memory layer is named memory, of kind memory, mutable and hideable, with no provenance, and is made on the first write; it takes part in select and mask like any layer, so read-graph, search-nodes and open-nodes read it in context. Search runs over item values through an FTS5 index. create-entities makes an element in the memory layer for a name the map does not hold, D18; a relation shows at both the node it is from and the node it points to.
- Non-goal: It keeps no history and no provenance; memory is meant to be cheap to add and to fix.
- Ref path: src/metaform/modules/memory/__init__.py
- Ref spec: LAYER-012
- Ref spec: LAYER-013
- Ref spec: STORE-020

### agent orchestrator receives from work queue

- Receiver: `stakeholder.orchestrator.agent`
- Provider: `code.queue.work`
- Type: purpose
- Name: work records
- Purpose: Line up what needs doing on the parts of the map it concerns, what is specified and not built, what is broken, what is left over, so the work can be handed out and worked through until nothing is open.
- Function: Keeps each element's or join's condition, tbd, broken or cruft, as a work record beside the map, with a note of what and where and a task of what it needs, held until agents take it, marked reviewed once checked, and done with its resolution kept; every read of an object carries its open conditions.
- EF: Function
- Relation: keeps each part's condition as a work record beside the map, open until its task is done
- Verb: keeps
- Observation: The work table, STORE-042, written through map_work op=add, edit and done and listed with op=list by condition or node, by any agent at any time; the intake agent writes them as it maps and intake_finish counts the open ones. A work record has no layer and never changes the map or counts as a correction. The web GUI draws a node with an open tbd at 70% opacity and flashes one with an open broken record red. helloworld's todo and done show it from a module.
- Non-goal: It does not hold the map's shape; the intended shape stays in the map and only the difference is recorded here.
- Ref spec: MAP-046
- Ref spec: STORE-042

### agent orchestrator receives from blind_spot analysis

- Receiver: `stakeholder.orchestrator.agent`
- Provider: `code.analysis.blind_spot`
- Type: purpose
- Name: blind-spot challenge
- Purpose: Find what the design lacks, functions and encounters the system should have and does not, from critics who own nothing they judge, and have each finding answered by the project so no later agent raises it again as if it had been missed.
- Function: Keeps each critic's challenges as items of its own blind-spot layer, whose one provenance record says whether the critic saw only the map or the map with the code, and records each answer beside that layer: A not beneficial, B beneficial, C handled by a named element or join.
- EF: Function
- Relation: keeps each critic's challenges in a layer of its own and records every answer, A, B or C, beside it
- Verb: keeps
- Observation: challenges.py and the map verbs answer and approve; a C without the link to what handles it is stored with a notice, and states are open, A, B, C and plan, STORE-040. There is one Inference Metaform and two types of blind spot analysis, metaform-only by a blinded critic and metaform plus code by a sighted one, each run its own layer, LAYER-014; comparing them is selecting both. The critic writes its layer with map_knowledge like any knowledge layer.
- Non-goal: The critic answers none of its own challenges, and the answering agent approves none of its own answers.
- Ref path: src/metaform/data/challenges.py
- Ref spec: LAYER-014
- Ref spec: LAYER-015

### agent orchestrator receives from instruction composer

- Receiver: `stakeholder.orchestrator.agent`
- Provider: `code.composer.instruction`
- Type: purpose
- Name: agent instructions
- Purpose: Learn on first contact with a project what Metaform is, what each module on its surface is for, and the one next step, such as having a subagent perform the intake by name, without reading any module's help first.
- Function: Composes the instructions live from the chassis's base text, the stop rule, each surfaced module's purpose under its id and each module's status notice, and gives that one text as the MCP server's instructions and as metaform help agents, which status points to.
- EF: Function
- Relation: composes the agent instructions live from each surfaced module's purpose and status notice
- Verb: composes
- Observation: instructions.py; module status hooks run in module id order, BASE-035: the intake's notice to delegate the intake appears while the project has none, and the web module's notice to start the web GUI before an intake while --web-autostart is on. The feedback request is added only while --debug is on. With no project for the folder, the text lists the registered projects and how to register one. Nothing is cached in files, so enabling, disabling or narrowing shows on the next read, MCP-007.
- Non-goal: It never copies a module's instructions anywhere that could go stale, and the skill carries none of them.
- Ref path: src/metaform/instructions.py
- Ref spec: MCP-007
- Ref spec: MCP-008
- Ref spec: MCP-009

### agent orchestrator receives from variant store

- Receiver: `stakeholder.orchestrator.agent`
- Provider: `code.store.variant`
- Type: purpose
- Name: origins and variants
- Purpose: Keep what every worker produced in its worktree or workfolder, committed or not, against one baseline, and bring any of those results back out anywhere, even without git or the repository.
- Function: Establishes an origin from a repository's commit or a full copy of a plain folder, collects any folder as a variant that stores only the files differing from its origin, whole while the variant's changed text is under 3 MB and as git diffs from there, binaries whole, and reconstructs one, several or every variant with Python alone, checking every file against its recorded hash.
- EF: Function
- Relation: stores each worker's result as the files that differ from one origin and rebuilds any of them with Python alone
- Verb: stores
- Observation: data/history.py; rows in projects/<project>/history.sqlite3 and payloads under ~/.metaform/origins/<mform_sha_id>/. metaform add origin, list origins, add variant <folder> [origin=] [remove=true] with provenance nouns, list variants and extract, also tools while the chassis is on the surface. The boundary is git ls-files --cached --others --exclude-standard, or a walk of a plain folder. A dirty working tree becomes the first variant, v000001; remove=true removes a git worktree only after its variant reconstructs what it held. Clearing a project keeps its history.
- Non-goal: It never makes one variant the baseline of another; only a new origin moves the baseline.
- Ref path: src/metaform/data/history.py
- Ref spec: PROJ-012
- Ref spec: PROJ-016
- Ref spec: PROJ-018

### agent orchestrator receives from specification

- Receiver: `stakeholder.orchestrator.agent`
- Provider: `document.specification`
- Type: purpose
- Name: the spec
- Purpose: Hand every builder agent one contract to build Metaform from, each requirement with its reason, its build detail and the tests that protect it, so no builder has to guess, choose or reinterpret.
- Function: Holds about 230 records in nine sections, the map, layers, storage, chassis and modules, command line and settings, MCP and the installer, quality, projects and the viewer, each with its requirement, what it means, why, how it shows, its build, its acceptance tests, its relations and its status, with one build order and every open question listed once.
- EF: Function
- Relation: holds each requirement with its reason, its build and the tests that protect it, as one contract a builder builds from alone
- Verb: holds
- Observation: specifications/spec, starting at 00-index.md. Where the spec and any code, test or older document differ, the spec wins, and Rich's design wins over the spec. Status is confirmed, recommended, open or deferred; a recommended record is built as written and an open one only as far as it is settled. It is frozen for the first release. BUILD-BRIEF.md tells a builder to write each step's tests first, see them fail, and report to the orchestrator; the cold build check, QUAL-011, runs a fresh agent over the spec until it finds nothing to guess.
- Non-goal: It records Rich's design and decides none of it; an open question blocks only the records that depend on it.
- Ref path: specifications/spec/00-index.md
- Ref path: specifications/spec/BUILD-BRIEF.md
- Ref spec: QUAL-011

#### Subtype: quality standard

- Provider: `document.standard.quality`
- Name: code quality standard
- Function: Sets the bar all code is judged against: organized by ownership, typed wherever an interface crosses a boundary, explicit about lifecycle and failure, free of hidden coupling, leaked resources and corrupted state, built from small cohesive parts, and carrying no architecture for a hypothetical need.
- EF: Function
- Relation: sets the bar each change is judged against, item by item, before it merges
- Verb: sets
- Observation: specifications/code_quality_standards.md, 22 lines, kept word for word, QUAL-001; a critic agent reviews each change against it, QUAL-008, and the reviews are kept as specifications/spec/REVIEW-CODE*.md.
- Ref path: specifications/code_quality_standards.md
- Ref spec: QUAL-001
- Ref spec: QUAL-008

#### Subtype: decision record

- Provider: `document.record.decision`
- Name: design record
- Function: Records every design point settled in conversation with the record that carries it, later decisions outranking earlier ones, beside the source requirements, their trace into the records, the evidence that an address alone carries inference, and every open question with a recommendation.
- EF: Function
- Relation: records each design decision with the record that carries it, later decisions outranking earlier ones
- Verb: records
- Observation: specifications/spec/CAPTURE.md, SETTLED.md, OPEN-QUESTIONS.md, REQUIREMENTS.md with REQUIREMENTS-corrections.md, spec/TRACE.md, and metaprompting_element_segments_example.md, whose four best-practice lists came from addresses alone, code through code.engine.game.fps. CAPTURE's entries from 09-26 and 09-27 are under discussion and placed in no requirement yet.
- Ref path: specifications/spec/CAPTURE.md
- Ref path: specifications/spec/OPEN-QUESTIONS.md
- Ref path: specifications/metaprompting_element_segments_example.md

#### Subtype: build record

- Provider: `document.record.build`
- Name: build record
- Function: Records each build step with the records it satisfies and the tests that protect them, and each critic review, test-gaming review, manual test and cold build check with what it found and what was done about it.
- EF: Function
- Relation: records each build step and each review with what it found and what was done about it
- Verb: records
- Observation: specifications/spec/BUILD-LOG.md through step 62, REVIEW-CODE rounds 1 to 7, TEST-REVIEW 1 to 8, MANUAL-TEST 1 to 5, COLD-BUILD 1 to 3 and HANDOFF.md.
- Ref path: specifications/spec/BUILD-LOG.md
- Ref path: specifications/spec/HANDOFF.md

#### Subtype: collaboration guide

- Provider: `document.guide.collaboration`
- Name: CLAUDE.md
- Function: Tells every agent developing Metaform how to work on it with Rich: ask when ambiguity changes the outcome, match complexity to the problem, keep scope, keep his wording, add no gate to prompted outputs, write tests first from the requirements, keep everything cross-platform, and carry the MetaformFoundation only into prompts for expert agents building the platform, never into intake.
- EF: Function
- Relation: tells every agent developing Metaform how to work on it, and keeps the expert foundation out of intake
- Verb: tells
- Observation: CLAUDE.md at the repository root, tracked; it states that its instructions are for agents developing or collaborating on the project, not for agents in the runtime. HANDOFF.md adds that an intake of this repository runs on a clean copy outside it, so this file never reaches the intake agent.
- Ref path: CLAUDE.md

### agent orchestrator receives from workflow engine

- Receiver: `stakeholder.orchestrator.agent`
- Provider: `code.engine.workflow`
- Type: purpose
- Name: workflow module
- Purpose: Run an authored workflow in any host that can run an agent, deciding when handing a step to another agent helps and whether that agent is blind to the repository, with every step carrying the context it needs.
- Function: Runs authored workflows as a module on the common base: it declares the --workflow setting and its abort verb, hands each step to an agent with the layers of inference it needs collected in advance, narrows each worker's folder, and keeps receipts for the work it tracks as layers.
- EF: Function
- Relation: runs an authored workflow step by step, handing each step to an agent with the context it needs
- Verb: runs
- Observation: Designed and not built: src/metaform/modules holds no workflow module, and its spec is deferred by D44, carrying REQ-140 to 150. CLI-021 names --workflow as the workflow module's own setting; the chassis runs no workflow, BASE-003; receipts belong to this module, BASE-030. Workflows written this way carry their own context, so they run in any host, LAYER-017.
- Non-goal: It never lives in the chassis, and the event bus never becomes its engine.
- Ref spec: LAYER-017
- Ref spec: CLI-021
- Ref spec: BASE-033

#### Subtype: prompt preprocessor

- Provider: `code.preprocessor.prompt`
- Name: lexicalization
- Function: Rewrites a prompt or workflow so it speaks to the project in its own names, follows each instruction with the namespace addresses it concerns as a footer pointing into the MCP server, and places the knowledge layers the orchestrator chose between the prompt and that footer, without changing the task.
- EF: Function
- Relation: rewrites a prompt in the project's own names and ends each instruction with the addresses it concerns
- Verb: rewrites
- Observation: LAYER-017, confirmed as design and deferred to the workflow module's spec. The chassis already supplies the reads it needs: readings and short names, the where read of an address, the layers at a node and the selection. The README calls the lexicalization producer intended functionality, not a shipped command.
- Ref spec: LAYER-017
- Ref path: README.md

### agent orchestrator receives from question channel

- Receiver: `stakeholder.orchestrator.agent`
- Provider: `code.channel.question`
- Type: purpose
- Name: questions at nodes
- Purpose: Ask the person for clarification at the part of the map a question concerns and carry on with what does not depend on the answer, so no work stops to wait.
- Function: Keeps each question or request for clarification at its node, makes the node glow while it is open, bright enough to see with the whole map zoomed out, and lets the person answer it in the web GUI, where a Messages button flies to the node of the oldest open question.
- EF: Encounter
- Relation: adds a question at the node it concerns and carries on while the person answers it in the web GUI
- Verb: adds
- Observation: Designed and not built: specifications/spec/CAPTURE.md, 09-26 and 09-27, under discussion and placed in no requirement; it touches VIEW-009 and VIEW-011, which today allow the page no write of this kind.
- Non-goal: It never blocks the asking agent.
- Ref path: specifications/spec/CAPTURE.md

### agent orchestrator receives from namespace tree

- Receiver: `stakeholder.orchestrator.agent`
- Provider: `data.tree.namespace`
- Type: purpose
- Name: namespace
- Purpose: Have each agent grasp what a part is at the level of type understanding, from an address it reads as a proper noun, before it reads any implementation.
- Function: Names every part by a dotted address whose prefixes are each a complete type in a tree under five roots, code, document, media, data and stakeholder; the address reads reversed as its name, name_length cuts it to a short name, and what holds at a prefix holds for every address toward the leaves.
- EF: Function
- Relation: names each part by an address that reads reversed as a proper noun, every prefix of it a type of its own
- Verb: names
- Observation: data/names.py computes reading and short_name, never stored as identity; data/roots.json holds the roots as data, so changing them needs no code; the store's types table keeps a row for every address in use and each prefix, with its parent. The store checks only the address form, lowercase letters, digits and underscores between periods, and never judges whether an address is functional, MAP-013; the intake's naming rules govern what the intake places. An element's identity belongs to its address, so an element cannot be moved.
- Non-goal: It holds no medium, encoding, genre or style in the functional map's addresses; knowledge layers may use any address.
- Ref path: src/metaform/data/names.py
- Ref spec: MAP-010
- Ref spec: MAP-011
- Ref spec: MAP-012

## project owner

- Address: `stakeholder.owner.project`
- Role: VE
- name_length: 2

### project owner receives from project registry

- Receiver: `stakeholder.owner.project`
- Provider: `code.registry.project`
- Type: purpose
- Name: registering and clearing a project
- Purpose: Bring a workpiece under Metaform by its folder and what it is, and take its map again from nothing whenever the intake should be redone, while the workpiece's files, settings and history stay as they are.
- Function: Registers a folder as a project with its target, path, url, artifact, inline or inferred, and clears a project on confirmation, removing its metaforms and reports and keeping its registration, folder, settings, origins and variants.
- EF: Encounter
- Relation: registers a workpiece by its folder and target, and clears its metaforms whenever it wants the intake taken again
- Verb: registers
- Observation: metaform add project <id> <path> [<target type> <target value>]; the same id and path twice is a no-op, a different path or a second id on one path is refused with a next step, STORE-031. Clearing is the standing request behind PROJ-025, on the command line, over MCP as clear_project and on the web GUI.
- Non-goal: Clearing never touches the project's folder, its settings or its history of origins and variants.
- Ref spec: STORE-031
- Ref spec: MAP-041
- Ref spec: PROJ-025

#### Subtype: project reset

- Provider: `code.reset.project`
- Name: clear project
- Function: Says exactly what clearing removes and keeps, and with --confirm removes every metaform of the project with its store and every report file, names each file it could not remove with the system's reason and what to do, and fires map.changed so open pages show the project with no metaform.
- EF: Function
- Relation: removes a project's metaforms and reports after saying what goes and what stays, and names whatever it could not remove
- Verb: removes
- Observation: home.to_clear and home.clear_project; metaform clear project [<project>] --confirm, the tool clear_project with confirm true, and the web GUI's Clear project action all call the same operation. Exit 0 even when a file stays, such as a store a running web GUI holds open on Windows; running it again removes what was left. Counts read as words: no metaforms, one report file.
- Ref path: src/metaform/home.py
- Ref spec: PROJ-025
- Ref spec: VIEW-019

### project owner receives from feedback channel

- Receiver: `stakeholder.owner.project`
- Provider: `code.channel.feedback`
- Type: purpose
- Name: reports
- Purpose: Hear from the agents working on its project, in their own words, what they found wrong with the project and with Metaform, and read any result an agent could not submit.
- Function: Keeps every report, feedback and shape file in the home and lists them by kind and layer and returns each exactly, through commands and tools that stay available whatever the command surface.
- EF: Encounter
- Relation: reads each report, feedback and shape file an agent left, listed by kind and by layer
- Verb: reads
- Observation: reports.py; metaform feedback <text> [layer=] [report=] [shape=], metaform list reports and metaform read report, and the tools feedback, list_reports and read_report, always listed. --report, on by default, asks the intake agent for a project report; --debug, off by default, asks every agent for process feedback. An agent that cannot continue stops and submits a trouble report with its result in shape=, and never retries, BASE-044. Without a project, files go to <home>/reports/.
- Non-goal: Nothing submitted is refused, and the settings decide only what agents are asked for, never what is kept.
- Ref path: src/metaform/reports.py
- Ref spec: BASE-044
- Ref spec: BASE-045
- Ref spec: CLI-034

### project owner receives from blind_spot analysis

- Receiver: `stakeholder.owner.project`
- Provider: `code.analysis.blind_spot`
- Type: purpose
- Name: approve
- Purpose: Decide which of the project agent's beneficial answers become new work, since agreeing to new work is the owner's decision.
- Function: Turns a challenge answered B into a plan, with the new element and join the critic proposed, from the command line only, so no agent working over MCP can approve its own answer.
- EF: Encounter
- Relation: approves a challenge answered B on the command line, and it becomes a plan with the element and join it proposed
- Verb: approves
- Observation: metaform map approve <challenge> is declared with surfaces=('cli',) and is absent from the MCP tool list; it refuses a challenge that is open or answered A or C, the one check kept because a person runs it. A plan an agent adds directly with op=add-plan needs no approval. The blind-spot layer's own items are never edited by an answer or an approval.
- Ref spec: LAYER-015
- Ref spec: STORE-040

### project owner receives from map viewer

- Receiver: `stakeholder.owner.project`
- Provider: `code.viewer.map`
- Type: purpose
- Name: web GUI
- Purpose: Watch the map of any registered project take shape as the intake records it, check every object's words, purposes, functions, observations, conditions and provenance in one place that shows exactly what agents would receive, and improve the prompts that made its layers.
- Function: Draws a project's active metaform as a floating 3D graph, each join in its tripartite form of receiver, purpose vertex and provider with layers as colors, beside a 2D map of the whole with short names that the camera walks node to node, an inspector holding the selected object's full record, and tabs for provenance, prompts and corrections; it follows an intake live as each object is recorded.
- EF: Encounter
- Relation: watches the map grow as the intake records it and selects any node to read its full record
- Verb: watches
- Observation: modules/web: page/app.js, 1391 lines, index.html and app.css, with 3d-force-graph 1.73.4 carrying three.js r168, Mermaid 12.0.0, CodeMirror 5.65.16 and IBM Plex bundled in vendor/ under a default-src 'self' policy, so nothing loads from the network. Entering a node replaces the 2D map with that node's own graph; in 3D every item of the layers turned on is its own node. A node with an open tbd record is drawn at 70% opacity and one with an open broken record flashes red. It writes exactly four things: the layer choice to the folder's --layers, a prompt's next version, removal of the top correction layer after a warning, and a project clear. Browser checks run through Playwright in CI; a person's look on macOS and Windows is still to do, MANUAL-TEST-5.
- Non-goal: Viewing never changes a setting or the map; memories, answers, knowledge and corrections are written through the tools, not the page.
- Ref path: src/metaform/modules/web/page/app.js
- Ref spec: VIEW-001
- Ref spec: VIEW-005
- Ref spec: VIEW-011

#### Subtype: web server

- Provider: `code.server.web`
- Name: web server
- Function: Serves the GUI for every registered project from one server per home on one fixed port, 7433 by default, detached from the terminal; answers only requests whose Host is its own and writes whose Origin is its own, asks for a token only off loopback, maps each /api/<read> onto one store read, and pushes each map.changed to every open page over a server-sent events stream.
- EF: Function
- Relation: serves every project's GUI from one server per home and pushes each change to every open page
- Verb: serves
- Observation: modules/web/server.py on the standard library's ThreadingHTTPServer. metaform web, or the tool web_start, starts it or reports the address it already runs at; metaform web stop ends it; run/web.json records its address and process. It waits in select with no timeout and never polls, QUAL-015. --web-port and --web-bind are home-wide settings.
- Ref path: src/metaform/modules/web/server.py
- Ref path: src/metaform/modules/web/__init__.py
- Ref spec: VIEW-002
- Ref spec: VIEW-004

#### Subtype: prompt editor

- Provider: `code.editor.prompt`
- Name: prompt editor
- Function: Opens a stored prompt's exact version in a text editor with XML and Markdown highlighting, search and replace, undo and line numbers, shows a line diff against the version it came from, and saves an edit as the next version without changing any earlier one.
- EF: Function
- Relation: saves an edited prompt as its next version and never changes the version a layer was made from
- Verb: saves
- Observation: The Prompt tab in page/app.js on CodeMirror 5.65.16, saving through POST /api/save-prompt, VIEW-013. The Canonical Intake is never offered, since it is not a stored prompt. With no prompt in the store it has nothing to open.
- Ref path: src/metaform/modules/web/page/app.js
- Ref spec: VIEW-013

### project owner receives from user guide

- Receiver: `stakeholder.owner.project`
- Provider: `document.guide.user`
- Type: purpose
- Name: documentation
- Purpose: Understand what Metaform does for its workpiece and run it, from installing and connecting an agent to reading the first map, with every command runnable as written and every claim checkable against the source.
- Function: Leads from the README's account of the mechanism through four guides, getting started, working with Metaform, reading an Inference Metaform and extending it, to a worked walkthrough on a dated export of this repository's map, a technical reference and a preprint with its citation.
- EF: Function
- Relation: leads a reader from what Metaform is to a first map and on to reading, keeping and extending it
- Verb: leads
- Observation: README.md, 268 lines, keeps Rich's own passages, the Bruce Lee quote, What is Metaform, The name, What it does, Refactoring legacy code and Porting across languages, and its authorship section credits Rich as the method's independent developer. docs/README.md indexes the set. docs/examples/project-metaform.json is the 2026-09-26 export used by the walkthrough, labelled as that snapshot; docs/EDITION.md pins the documented source edition at commit ce9062b. Figures are Mermaid diagrams and a screenshot of the web GUI, never ASCII drawings.
- Non-goal: It never presents intended functionality as shipped; lexicalization and automated blind-spot production are described as mechanisms, not commands.
- Ref path: README.md
- Ref path: docs/README.md
- Ref path: docs/guides

#### Subtype: research paper

- Provider: `document.paper.research`
- Name: preprint
- Function: Develops the full causal account of the method, advance inference amortization, type understanding through addresses, relational identity, Encounter propagation, lexicalization, provenance and formation through intent, with its connections to other work and how to cite it.
- EF: Function
- Relation: develops the complete causal account of the method for readers who need the mechanism, with how to cite it
- Verb: develops
- Observation: docs/preprint/inference-metaform.md, 434 lines, typeset as inference-metaform.pdf, with references.bib and CITATION.md; it credits Rich as independent developer and claims no DOI, license or peer review.
- Ref path: docs/preprint

#### Subtype: technical reference

- Provider: `document.reference.technical`
- Name: technical reference
- Function: Gives the full mechanisms and terminology, the source correspondence of each mechanism with its tests, the traces and measurements still worth collecting, and new tool proposals kept apart from what is built.
- EF: Function
- Relation: ties each mechanism to its source, its tests and the evidence still to collect
- Verb: ties
- Observation: docs/inference-metaform: REFERENCE.md 1030 lines, IMPLEMENTATION_MAP.md 768, EXAMPLES_TO_COLLECT.md with 16 collection targets, IDEAS.md with eight proposals.
- Ref path: docs/inference-metaform

#### Subtype: agent definition

- Provider: `document.definition.agent`
- Name: repo-presentation agent
- Function: Instructs a Claude Code agent to rewrite the README and docs so a reader understands Metaform on the first read, keeping Rich's passages word for word, one vocabulary, the tree's direction words, rendered figures and every claim checked against the source, without touching code, tests or specifications.
- EF: Function
- Relation: instructs an agent to keep the README and docs readable and true to the source without touching the code
- Verb: instructs
- Observation: .claude/agents/repo-presentation.md, model sonnet; it lists the facts that changed since commit ce9062b and requires every command to be checked in a throwaway METAFORM_HOME.
- Ref path: .claude/agents/repo-presentation.md

## context engine

- Address: `code.engine.context`
- Role: AUE
- name_length: 2
- Ref path: src/metaform
- Ref path: specifications
- Ref path: docs
- Ref path: tests
- Ref path: README.md
- Ref path: pyproject.toml
- Ref path: .github/workflows/checks.yml

### context engine receives from chassis

- Receiver: `code.engine.context`
- Provider: `code.chassis`
- Type: purpose
- Name: Metaform
- Purpose: Prepare a workpiece's functional understanding once, before the work, and hand it to every later agent, session and operation, so the inference an agent would spend orienting itself is spent in advance and amortized.
- Function: Holds the functional map and every layer over it as one working base that runs alone as a command line and carries every other capability, the intake, map reads and writes, memory, the MCP server and the web GUI, as modules loaded onto it.
- EF: Function
- Relation: holds the functional map with its layers and carries every other capability as a module loaded onto it
- Verb: holds
- Observation: src/metaform holds the chassis and seven shipped modules, five on by default: intake, map, mcp, memory and web; helloworld and template ship disabled. specifications/spec holds the contract the build follows, about 230 records in nine sections. tests/ holds 21 chassis test files and each module keeps its own tests; 564 tests outside the web module pass on Linux. Package metaform 0.1.0, Python 3.11 or newer, one chassis dependency, prompt_toolkit. The workpiece mapped may be any artifact, code or not, MAP-041.
- Ref path: src/metaform
- Ref path: src/metaform/modules
- Ref path: specifications/spec
- Ref path: specifications/Canonical_Intake.xml
- Ref path: tests
- Ref path: docs
- Ref path: README.md
- Ref path: pyproject.toml
- Ref path: .github/workflows/checks.yml
- Ref path: conftest.py

## chassis

- Address: `code.chassis`
- Role: DE
- name_length: 1
- Ref path: src/metaform/cli.py
- Ref path: src/metaform/home.py
- Ref path: src/metaform/data
- Ref path: src/metaform/loader.py
- Ref path: specifications/spec/04-chassis-modules.md
- Serves: agent orchestrator `stakeholder.orchestrator.agent`, context engine `code.engine.context`

### chassis receives from graph store

- Receiver: `code.chassis`
- Provider: `code.store.graph`
- Type: purpose
- Name: data access object
- Purpose: Own every piece of Metaform data in one place that the command line, MCP and every module reach the same way, so nothing a module keeps is lost, leaks between projects or slips past what an agent is allowed to see, and a project can be carried whole to another home.
- Function: Stores each metaform as one SQLite file holding one row per thing, reached only through the Store object: elements by address, joins owned by their receiver, subtype joins inside their join, refs, layers, items, properties and work records; each write is one transaction and each read goes through an index, with select, mask and hiding applied inside the read.
- EF: Function
- Relation: stores each metaform as one row per thing in its own SQLite file and answers every read through an index, applying select, mask and hiding inside the read
- Verb: stores
- Observation: src/metaform/data: store.py is the one public door; writes.py, reads.py, layering.py, corrections.py and challenges.py each take its open transaction; schema.py is layout version 5 and a store written before step 52 is refused. Every SQLite file opens through sqlite.opened under a per-file lock, in WAL with a 30 s busy timeout. A write that does not fit is stored as given with a notice; only an unreadable call, an unknown reference or a newer schema raises StoreError, STORE-026. An element is its address, name_length and role and cannot be moved; a join keeps its id when it moves.
- Non-goal: It offers no general SQL surface and never judges whether an address is functionally valid.
- Ref path: src/metaform/data/store.py
- Ref path: src/metaform/data/schema.py
- Ref path: src/metaform/sqlite.py
- Ref spec: STORE-023
- Ref spec: STORE-026

#### Subtype: project exchange

- Provider: `code.exchange.project`
- Name: export and import
- Function: Writes a project, or chosen metaforms and layers of it, to one JSON document in which every row carries its identity id and layer id, and imports only what the target does not already hold, one transaction per metaform.
- EF: Function
- Relation: writes a project to one JSON document by unique id and adds back only what the target does not hold
- Verb: writes
- Observation: data/exchange.py; metaform export [<project>|all] [file=] [metaform=] [layer=]... and metaform import <file> [<project>]. A layer or thing whose id exists is skipped, so importing twice adds nothing, STORE-027; a layer-limited export lists what it requires from other layers. The same code reads a directly run wheel's home for metaform import wheel=<name>-<version>, arriving as new metaforms, never merged, BASE-025.
- Non-goal: It is not backup and restore, which are not specified yet, and it never imports an intake answer; the intake agent writes the map through the intake tools.
- Ref path: src/metaform/data/exchange.py
- Ref spec: STORE-027
- Ref spec: BASE-025

### chassis receives from plugin system

- Receiver: `code.chassis`
- Provider: `code.system.plugin`
- Type: purpose
- Name: modules and the common base
- Purpose: Carry every capability beyond its own commands as a separately owned module, so a module can be added, turned off or removed without the chassis naming it and without losing the data it kept.
- Function: Holds one module contract in metaform.module and loads each module as one owned unit: the verbs, settings, subscriptions and tasks it registers are recorded under its id, so unload, reload and shutdown withdraw all of them while its stored data stays.
- EF: Function
- Relation: loads each module as one owned unit and withdraws everything it registered when it goes, while its data stays
- Verb: loads
- Observation: module.py holds the contract and the public base, metaform.module, metaform.settings, metaform.data and metaform.events; loader.py loads. The chassis names no module: module state reaches status and the agent instructions only through each module's status hook, BASE-035. Seven modules ship in src/metaform/modules; helloworld and template declare SHIPS_DISABLED.
- Non-goal: It gives a module no private way to the data or the command line; whatever two modules need goes into the common base.
- Ref path: src/metaform/module.py
- Ref path: src/metaform/loader.py
- Ref spec: BASE-004
- Ref spec: BASE-018

#### Subtype: module loader

- Provider: `code.loader.module`
- Name: discovery and loading
- Function: Finds modules in the shipped folder, the home's modules folder and installed metaform.modules entry points, reads each one's SUPPORTED_OS, DEPENDENCIES and SHIPS_DISABLED literals by parsing its source without running it, and imports only the enabled, compatible ones whose dependencies are installed.
- EF: Function
- Relation: reads each module's declarations from its source before any of its code runs and imports only the enabled, compatible ones
- Verb: reads
- Observation: loader.py and module_metadata.py. Discovery runs once per process and is cached; enable and disable reset it. A reserved chassis name, a second module with one id, a missing SUPPORTED_OS, an uninstalled dependency, a bad tool name or an import error is shown by metaform list modules with its reason, and the module contributes nothing. A start hook that raises unloads its module; spawned tasks are cancelled and awaited before stop.
- Non-goal: It never imports a module to learn whether it is compatible.
- Ref path: src/metaform/loader.py
- Ref path: src/metaform/module_metadata.py
- Ref spec: BASE-015
- Ref spec: BASE-037

### chassis receives from command_line interface

- Receiver: `code.chassis`
- Provider: `code.interface.command_line`
- Type: purpose
- Name: metaform command
- Purpose: Run completely on its own from one command, so a person or an agent without MCP reaches every capability, every call reads the same way, and every failure names the one command to run next.
- Function: Reads each command line as a chassis verb, or a module id and its verb, with nouns and switches; runs chassis verbs itself and module verbs with their own Context; prints a verb's result as the same data MCP returns; and ends every error with one Error line and one Next line.
- EF: Function
- Relation: reads every command as a verb with its nouns and switches and ends every error with the one next step
- Verb: reads
- Observation: cli.py. metaform alone prints status in a fixed order of lines, CLI-028. Exit codes are 0 done, 1 failure, 2 user error, 3 cancelled and 130 interrupted; the first Ctrl+C asks an async verb to cancel and a second interrupts it. After every command the chassis fires map.changed for what the command changed. A folder's --modules narrows which groups show and run, while help, set, unset, config, feedback and read always run so the way back stays open.
- Non-goal: It never waits on a prompt without a terminal; anything a prompt would ask can be given on the command line.
- Ref path: src/metaform/cli.py
- Ref spec: CLI-001
- Ref spec: CLI-009
- Ref spec: BASE-031

#### Subtype: command parser

- Provider: `code.parser.command`
- Name: shared grammar
- Function: Parses required nouns in order, optional nouns as name=value words in any order, switches as settings and -- as the end of switches, and reads a tool call's JSON arguments by the same rules, so a text noun sent another JSON type reaches the verb as its JSON text with a notice.
- EF: Function
- Relation: parses a call by the same rules whether it arrives as words on the command line or as JSON over MCP
- Verb: parses
- Observation: grammar.py, used by cli.run_module and by the MCP server through module.tool_arguments. An unknown name=value word is kept in the record's extra with a notice, BASE-043; an int or bool that cannot be read stops the call with the command line's next step, BASE-035 and MCP-005.
- Ref path: src/metaform/grammar.py
- Ref spec: BASE-043
- Ref spec: CLI-003

#### Subtype: help system

- Provider: `code.system.help`
- Name: help
- Function: Builds the overview, the commands and switches indexes and every command, module, verb and switch page from the live declarations, with --help and -h giving only the syntax.
- EF: Function
- Relation: builds every help page from the live declarations, so no module writes help anywhere else
- Verb: builds
- Observation: docs.py; the overview fits one screen and ends with tips, CLI-006; pages follow one layout, CLI-029; a verb outside this system is listed under Not on this system with where it runs, BASE-016.
- Ref path: src/metaform/docs.py
- Ref spec: CLI-007
- Ref spec: CLI-029

#### Subtype: query

- Provider: `code.query`
- Name: query
- Function: Answers each of the design's own questions with one store read from the command line, element, joins, identity, where, node, context, layer items, links, citing, search, history, stack and the rest, with no module enabled.
- EF: Function
- Relation: answers each of the design's questions with one store read, with no module needed
- Verb: answers
- Observation: query.py; metaform query alone lists the reads; a read's options are name=value nouns and its only switch is --json; there is no free SQL, so select, mask and hiding hold on this path too, STORE-028.
- Ref path: src/metaform/query.py
- Ref spec: STORE-028

### chassis receives from settings system

- Receiver: `code.chassis`
- Provider: `code.system.settings`
- Type: purpose
- Name: settings
- Purpose: Let every behavior a person or an agent can ask for once also be a standing choice, declared once, that works with no configuration and survives a module being turned off.
- Function: Keeps one schema of settings declared in code by the chassis and each module, and resolves each value from the switch on this call, then the value stored at the nearest folder at or above this one, then the declared default; it stores only what was set, with glue that keeps a value through unset all.
- EF: Function
- Relation: resolves each setting from this call's switch, then the nearest folder's stored value, then its declared default
- Verb: resolves
- Observation: settings.py. Every long switch is a setting: passed on one call, stored with metaform set, cleared with unset, protected with --glue, and inverted by its opposite form; booleans have --name and --no-name and never toggle; --confirm is never a setting. Stored rows are keyed by scope, owner and key in the base database, so a disabled module's values return with it, CLI-024. The chassis declares project, modules, layers, debug and report.
- Non-goal: It never writes a default into storage, so a later release's default reaches every folder still at default.
- Ref path: src/metaform/settings.py
- Ref spec: CLI-010
- Ref spec: CLI-013
- Ref spec: CLI-023

#### Subtype: settings screen

- Provider: `code.screen.settings`
- Name: settings screen
- Function: Lists the chassis and every discovered module with each setting's value and state, and stages edits, resets, glue and module enable or disable until they are previewed and saved, through the same parser as set.
- EF: Function
- Relation: stages every change to settings and modules until it is previewed and saved
- Verb: stages
- Observation: tui.py on prompt_toolkit, opened by metaform config only when standard input and output are terminals; otherwise config prints what config --show prints. Quitting with unsaved changes asks to save, discard or continue, CLI-026.
- Ref path: src/metaform/tui.py
- Ref spec: CLI-026

### chassis receives from project registry

- Receiver: `code.chassis`
- Provider: `code.registry.project`
- Type: purpose
- Name: home
- Purpose: Know every registered project, the folder each agent works from, and which of a project's metaforms is active, without writing anything into any project folder.
- Function: Keeps projects with their target, the working-folder table, settings and module state in the home's base database, resolves a folder to its project by its stored project setting or else the deepest registered path containing it, and keeps each project's metaforms with exactly one active.
- EF: Function
- Relation: resolves each folder to its project, and each project to its active metaform, from the home alone
- Verb: resolves
- Observation: home.py and context.py; the base database is <home>/metaform.sqlite3, layout version 1; each metaform's store is projects/<project>/metaforms/<metaform id>/store.sqlite3. A project id is lowercase letters, digits, _ and -, up to 64. A folder row is written only when a setting is stored for it. Resolution runs per call, so an MCP server started outside every project serves one after the set tool selects it, PROJ-005. A second intake into a metaform that has one is recorded in a new metaform, activated at its finish, MAP-045.
- Non-goal: It keeps no marker, cache or database in a project folder.
- Ref path: src/metaform/home.py
- Ref spec: STORE-002
- Ref spec: STORE-041
- Ref spec: PROJ-003

### chassis receives from event bus

- Receiver: `code.chassis`
- Provider: `code.bus.event`
- Type: purpose
- Name: event bus
- Purpose: Let modules act on what happened elsewhere, a greeting recorded, a map changed, without importing each other and without any module having to announce its own writes.
- Function: Delivers a published topic to every enabled module subscribed to it, each with its own Context built from the publisher's folder and project and a copy of the payload, and returns each delivery's outcome, completed, failed or cancelled, so one subscriber's failure never hides another's.
- EF: Function
- Relation: delivers each published topic to every subscribed module with a Context of its own and returns every delivery's outcome
- Verb: delivers
- Observation: events.py: ctx.publish from a plain verb, await ctx.publish_async from an async one, which runs a plain subscriber in a worker thread; publish inside a running loop raises and names publish_async. Subscribers today: helloworld on helloworld.greeted, web on map.changed.
- Non-goal: It runs no workflow: no retry, no delay, no ordering beyond declaration order and no persistent queue, BASE-033.
- Ref path: src/metaform/events.py
- Ref spec: BASE-010
- Ref spec: BASE-032
- Ref spec: BASE-033

#### Subtype: change announcer

- Provider: `code.announcer.change`
- Name: map.changed
- Function: Collects the notes the store makes of each committed write that changed rows and the home makes of each metaform added, removed or made active, and when a command ends, on the command line, over MCP or as one of the web GUI's writes, fires map.changed once per metaform changed, with the project and the metaform's id.
- EF: Function
- Relation: fires map.changed once for each metaform a finished command changed
- Verb: fires
- Observation: changes.py, called from cli.main, after each MCP tool call in a worker thread, and by the web server after its writes. A command that only reads fires nothing. Work a module does in a task it spawned is announced only if the module publishes map.changed itself, VIEW-018.
- Ref path: src/metaform/changes.py
- Ref spec: VIEW-018

## blind_spot analysis

- Address: `code.analysis.blind_spot`
- Role: SE
- name_length: 2
- Ref path: src/metaform/data/challenges.py
- Work record, tbd: Only the chassis side is built: challenge states, answer, approve and plans. LAYER-015's Build calls for a critic prompt that gives the metaform and asks for blind spots and an answer prompt that gives each challenge with the three answers as equals; neither exists, no module runs a blinded or sighted critic, and a blind-spot layer is any layer of kind layer, told apart by nothing. prompts.shipped has no caller. CAPTURE 09-27 adds, under discussion, the entries' looks: red at 70% opacity, green when useful, yellow when not, with the owner's veto. Task: Write the critic and answer prompts and the module or workflow that runs a blinded and a sighted critic, each into its own layer; settle the node looks with Rich.
- Serves: agent orchestrator `stakeholder.orchestrator.agent`, project owner `stakeholder.owner.project`

## change announcer

- Address: `code.announcer.change`
- Role: SE
- name_length: 2

## map api

- Address: `code.api.map`
- Role: SE
- name_length: 2
- Ref path: src/metaform/modules/map
- Serves: agent orchestrator `stakeholder.orchestrator.agent`

## bootstrap

- Address: `code.bootstrap`
- Role: SE
- name_length: 1

## package builder

- Address: `code.builder.package`
- Role: SE
- name_length: 2
- Ref path: src/metaform/build.py
- Ref path: src/metaform/_build_info.py
- Work record, tbd: The published distribution name is undecided: the name metaform on PyPI belongs to an unrelated package, BASE-021, MCP-010 and section 04 question 4. Until it is decided, every registration points at a local wheel path. Task: Decide the PyPI distribution name; then the installer registers it in place of the path.
- Serves: installer `code.installer`, agent host `stakeholder.host.agent`

## event bus

- Address: `code.bus.event`
- Role: SE
- name_length: 2
- Ref path: src/metaform/events.py
- Ref path: src/metaform/changes.py
- Serves: chassis `code.chassis`, map viewer `code.viewer.map`

## feedback channel

- Address: `code.channel.feedback`
- Role: SE
- name_length: 2
- Ref path: src/metaform/reports.py
- Serves: intake `code.intake`, project owner `stakeholder.owner.project`

## question channel

- Address: `code.channel.question`
- Role: SE
- name_length: 2
- Work record, tbd: Decided in conversation and not built: an agent adds a question at the node it concerns and carries on; the node glows while open; the person answers in the GUI; a Messages button in the 3D view flies to the oldest open question. CAPTURE 09-26 and 09-27, placed in no requirement; answering from the page would be a fifth write beyond VIEW-011's four. Task: Place the design in requirements with Rich, including the page's write, then build the question records, the glow and the Messages button.
- Serves: agent orchestrator `stakeholder.orchestrator.agent`

## traceability check

- Address: `code.check.traceability`
- Role: SE
- name_length: 2

## probe client

- Address: `code.client.probe`
- Role: SE
- name_length: 2

## instruction composer

- Address: `code.composer.instruction`
- Role: SE
- name_length: 2
- Ref path: src/metaform/instructions.py
- Work record, tbd: specifications/spec/CAPTURE.md, Suggesting layers, under discussion: when the main agent offers to start an intake, it suggests also creating a blind spot challenge and a knowledge layer that records best practices, and explains them when asked. The composed instructions and the intake's notice say nothing of it. Task: Settle the suggestion's wording and where it lives, in the intake's notice or a module's purpose, then add it.
- Serves: agent orchestrator `stakeholder.orchestrator.agent`

## module contract

- Address: `code.contract.module`
- Role: NE
- name_length: 2

## prompt editor

- Address: `code.editor.prompt`
- Role: SE
- name_length: 2

## workflow engine

- Address: `code.engine.workflow`
- Role: SE
- name_length: 2
- Work record, tbd: Specified as design and not built: the workflow module, its --workflow setting and abort verb, receipts, workflow intake and handoffs, D44 and REQ-140 to 150, and prompt and workflow preprocessing, lexicalization, LAYER-017. Open: whether abort is the workflow module's verb, section 05 question 8. Task: Write the workflow module's spec, D44, then build it and the lexicalization preprocessor on the common base.
- Serves: agent orchestrator `stakeholder.orchestrator.agent`

## project exchange

- Address: `code.exchange.project`
- Role: SE
- name_length: 2

## installer

- Address: `code.installer`
- Role: SE
- name_length: 1
- Ref path: src/metaform/install.py
- Ref path: src/metaform/probe.py
- Ref path: src/metaform/skill/SKILL.md
- Work record, tbd: The MCP registration of Copilot CLI, Factory and Antigravity and Factory's skill folder are unverified, E2; whether Claude Desktop is a target waits on D42; MCP-022's proof that each tool actually loads the skill from its folder needs each real tool and is not automated; whether uninstall offers to remove the home's data is open, section 06 question 9; whether install and uninstall stay chassis verbs is open, section 04 question 5. Task: Confirm each unverified tool's mechanism from its own documentation and offer it; decide D42 and questions 5 and 9; run MCP-022's verification per tool.
- Serves: agent host `stakeholder.host.agent`

### installer receives from package builder

- Receiver: `code.installer`
- Provider: `code.builder.package`
- Type: purpose
- Name: last build
- Purpose: Register a server that starts from a known wheel holding exactly the modules the user has enabled.
- Function: Writes one py3-none-any wheel of the chassis and every enabled module to ~/.metaform/builds/<UTC time>/ and records its path as last_build, which the installer registers as the uvx source unless Metaform is itself running from a wheel.
- EF: Function
- Relation: writes one wheel of the chassis and the enabled modules and records its path as the last build
- Verb: writes
- Observation: build.py writes the wheel itself with zipfile from the installed package, so no source tree is needed; each carried module goes in as a system module without its tests; entry_points.txt holds the metaform console script and one metaform.modules line per module; Requires-Dist is CHASSIS_DEPENDENCIES from _build_info.py plus each carried module's DEPENDENCIES, so a build without mcp lists no mcp, BASE-041. With no wheel, install stops with Next: metaform build, MCP-010.
- Ref path: src/metaform/build.py
- Ref spec: BASE-022
- Ref spec: BASE-041
- Ref spec: MCP-010

## intake

- Address: `code.intake`
- Role: SE
- name_length: 1
- Ref path: src/metaform/modules/intake
- Serves: agent orchestrator `stakeholder.orchestrator.agent`

### intake receives from intake procedure

- Receiver: `code.intake`
- Provider: `document.procedure.intake`
- Type: purpose
- Name: Canonical Intake
- Purpose: Hand every intake agent one fixed method for turning a workpiece into its functional map, the same text each time, so every map comes from the same procedure.
- Function: Defines the method: survey the artifact, infer the vested entities and the defining element, trace each receiver's operative purpose to the encounter functions that serve it, address every element by the namespace rules, record each object as it is reasoned, anneal parts into their parents' joins, and proof the map before finishing.
- EF: Function
- Relation: defines the method that turns a workpiece into its map, from its vested entities through each receiver's purpose to the functions that serve it
- Verb: defines
- Observation: specifications/Canonical_Intake.xml, process digital-typology version 1.1, 178 lines, with its concepts, vested entity rules, namespace rules with valid and invalid examples, the method's steps 1 to 12 and the response schema. The module's resource copy is byte-identical, which a repository test checks. It is served as shipped and never kept in the prompt store, so an intake layer's provenance keeps no copy, STORE-044; the folder setting intake_file serves another file for testing.
- Non-goal: It does not grade the map it produces; intake is never gated or judged.
- Ref path: specifications/Canonical_Intake.xml
- Ref spec: BASE-039
- Ref spec: STORE-016

### intake receives from feedback channel

- Receiver: `code.intake`
- Provider: `code.channel.feedback`
- Type: purpose
- Name: intake report and feedback
- Purpose: Keep the intake agent's report on the project and its feedback on the process with the intake layer's provenance, so each finding stays tied to the run that produced it.
- Function: Writes each text to its own file in the project's reports folder under the home, named by the layer's id and its kind, appends a timed section on a second write, and records a row that makes the file a ref on the layer's provenance.
- EF: Function
- Relation: writes the intake's report and feedback to files named by its layer and ties them to that layer's provenance
- Verb: writes
- Observation: intake_finish report= and feedback= call module.save_report; files are projects/<project>/reports/<layer id>-report.md and -feedback.md, one row each in the store's reports table, STORE-043; the finish returns the counts of elements, joins, subtype joins, refs and open work records.
- Ref path: src/metaform/reports.py
- Ref spec: BASE-045

### intake receives from graph store

- Receiver: `code.intake`
- Provider: `code.store.graph`
- Type: purpose
- Name: building intake layer
- Purpose: Keep a half-recorded map away from every agent until the intake finishes, and let the next agent resume an intake that an interrupted one left.
- Function: Keeps the intake layer building while it is recorded: its objects are written, edited, moved and removed in place, absent from every read in context and from has_intake, readable whole or by receiver through layer_graph and intake_recording, and fixed at the finish so that afterwards only a correction layer changes it.
- EF: Function
- Relation: keeps the intake layer building and out of every read in context until the intake finishes
- Verb: keeps
- Observation: STORE-032; kind intake, immutable, not hideable, variable 'The functional map of the artifact: its elements, and each receiver's purpose served by a provider's encounter function.', provenance module intake, workflow canonical-intake, prompt empty. Layer names read intake-<UTC time>-<6 hex>. After the finish, edit and absorb write nothing and name the correction layer.
- Ref spec: STORE-032
- Ref spec: BASE-039

## continuous integration

- Address: `code.integration.continuous`
- Role: SE
- name_length: 2

## command_line interface

- Address: `code.interface.command_line`
- Role: SE
- name_length: 2
- Ref path: src/metaform/cli.py
- Ref path: src/metaform/grammar.py
- Ref path: src/metaform/docs.py
- Ref path: src/metaform/results.py
- Ref path: src/metaform/query.py
- Serves: chassis `code.chassis`

## knowledge layer

- Address: `code.layer.knowledge`
- Role: SE
- name_length: 2
- Ref path: src/metaform/data/layering.py
- Ref path: src/metaform/data/selection.py
- Serves: agent orchestrator `stakeholder.orchestrator.agent`

### knowledge layer receives from prompt store

- Receiver: `code.layer.knowledge`
- Provider: `code.store.prompt`
- Type: purpose
- Name: prompt versions
- Purpose: Tie each layer to the exact prompt text it was made from, so a prompt can be improved for later runs while every existing layer still shows the text that produced it.
- Function: Keeps prompts in one store for the whole home as numbered versions that are never changed or deleted, a module's shipped text becoming version 1 when first served and flowing in until someone saves an edit, and records which version each layer was made from.
- EF: Function
- Relation: keeps every prompt as numbered versions that never change and records the version each layer was made from
- Verb: keeps
- Observation: data/prompts.py; ~/.metaform/prompts.sqlite3, layout version 1, with prompts, prompt_versions and prompt_uses, the last keyed by project, metaform and layer. metaform prompts and metaform prompt <name> [<version>], and the tools prompts and prompt, read it; a layer's provenance read returns prompt_version. The Canonical Intake is never kept here, STORE-044.
- Non-goal: It never edits a version in place; an edit is always the next version with its parent.
- Ref path: src/metaform/data/prompts.py
- Ref spec: STORE-044
- Ref spec: LAYER-010

## module loader

- Address: `code.loader.module`
- Role: SE
- name_length: 2

## agent memory

- Address: `code.memory.agent`
- Role: SE
- name_length: 2
- Ref path: src/metaform/modules/memory
- Serves: agent orchestrator `stakeholder.orchestrator.agent`

## example module

- Address: `code.module.example`
- Role: SE
- name_length: 2

## command parser

- Address: `code.parser.command`
- Role: SE
- name_length: 2

## prompt preprocessor

- Address: `code.preprocessor.prompt`
- Role: SE
- name_length: 2

## query

- Address: `code.query`
- Role: SE
- name_length: 1

## work queue

- Address: `code.queue.work`
- Role: SE
- name_length: 2
- Ref path: src/metaform/data/writes.py
- Ref path: src/metaform/modules/map/__init__.py
- Work record, tbd: specifications/spec/CAPTURE.md, 09-26 and 09-27, under discussion and placed in no requirement: the orchestrator writes each task's instructions on the nodes it touches; a work queue in the MCP server hands an agent a task with everything the map holds for those nodes and takes it off the list; a task whose agent dies stays taken, showing its age; each node shows the agent's progress sentence, so the map works as a kanban board; completed tasks become past work; items carry the flags task, read_first and always_show. Only the work records are built. Task: Settle this design with Rich and place it in requirements, then build the queue, the tasks on nodes and the progress labels.
- Serves: agent orchestrator `stakeholder.orchestrator.agent`

## project registry

- Address: `code.registry.project`
- Role: SE
- name_length: 2
- Ref path: src/metaform/home.py
- Ref path: src/metaform/context.py
- Serves: chassis `code.chassis`, project owner `stakeholder.owner.project`

## project reset

- Address: `code.reset.project`
- Role: SE
- name_length: 2

## settings screen

- Address: `code.screen.settings`
- Role: SE
- name_length: 2

## layer selection

- Address: `code.selection.layer`
- Role: SE
- name_length: 2

## mcp server

- Address: `code.server.mcp`
- Role: SE
- name_length: 2
- Ref path: src/metaform/modules/mcp
- Work record, tbd: MCP-011 is open: when a host starts the server with a working folder outside the project, or none, which project it serves has no confirmed design, D37. PROJ-005's rule, resolving the server's start folder per call and letting the agent select a project with the set tool, is built as the fallback. Task: Decide MCP-011, how the server knows the project the agent works in when the host starts it elsewhere.
- Serves: agent host `stakeholder.host.agent`

### mcp server receives from plugin system

- Receiver: `code.server.mcp`
- Provider: `code.system.plugin`
- Type: purpose
- Name: one declaration, one tool
- Purpose: Serve every module's verbs as tools with no MCP code written in any module, and never list or run a tool the folder's command surface hides.
- Function: Supplies the loaded modules on the folder's surface, in id order, with each verb's nouns, switches, caution, systems and surfaces, from which each tool's name <module>_<verb> and its input schema are built on every request.
- EF: Function
- Relation: supplies each surfaced module's verb declarations, from which every tool's name and input schema are built
- Verb: supplies
- Observation: module.surface and module.tool_arguments; server.verb_schema gives one property per noun typed by its kind, one per setting the verb reads, confirm on a caution verb, and project and layers on every tool, with additionalProperties false and each help text as its description, MCP-003. A verb declared for the command line only, or for other systems, is not listed; a call to a tool outside the surface returns an error naming metaform help commands.
- Ref path: src/metaform/module.py
- Ref path: src/metaform/modules/mcp/server.py
- Ref spec: MCP-003
- Ref spec: MCP-005

## web server

- Address: `code.server.web`
- Role: SE
- name_length: 2

## correction stack

- Address: `code.stack.correction`
- Role: SE
- name_length: 2
- Ref path: src/metaform/data/corrections.py
- Work record, tbd: specifications/spec/CAPTURE.md, 09-27 night: Rich's design reads no correction layers, changing the metaform is updating it, each change a new version of the object with provenance. It is marked not placed; the spec and code keep the correction stack, LAYER-011 and STORE-017. Task: Decide whether the correction stack stays or changing the metaform becomes versioned updates of each object, then bring the spec and the store to it.
- Serves: agent orchestrator `stakeholder.orchestrator.agent`

## graph store

- Address: `code.store.graph`
- Role: SE
- name_length: 2
- Ref path: src/metaform/data
- Ref path: src/metaform/sqlite.py
- Ref spec: specifications/spec/03-storage.md
- Work record, cruft: A .metaform/ folder sits untracked in the repository root, dated 2026-09-10 to 09-18: config.json, metaform.json, state.sqlite3, history/, home/, viewer logs, left by the runtime before the chassis. STORE-001 now writes nothing into a project folder, so git status in this project shows it as new. Task: Remove the repository root's .metaform/ folder once nothing in it is wanted; it is not read by the current chassis.
- Serves: chassis `code.chassis`, intake `code.intake`, map viewer `code.viewer.map`

## prompt store

- Address: `code.store.prompt`
- Role: SE
- name_length: 2
- Ref path: src/metaform/data/prompts.py
- Work record, broken: Not connected: outside tests nothing calls prompts.shipped, prompts.add_prompt or prompts.record_use. No module ships a prompt, and map_knowledge op=create prompt= keeps the text in the layer's provenance but links no version. So the store stays empty in use, every provenance read's prompt_version is empty, and the web GUI's Prompt tab and save, which need an existing prompt, have nothing to open. Task: Have each module that makes layers from a prompt serve it through prompts.shipped and record the version at layer creation, or decide how a prompt first enters the store, then connect provenance to it.
- Serves: knowledge layer `code.layer.knowledge`

## variant store

- Address: `code.store.variant`
- Role: SE
- name_length: 2
- Ref path: src/metaform/data/history.py
- Work record, tbd: Not built: exporting a whole origin unit as a wheel whose own command line reconstructs its variants, PROJ-020, and importing a unit, PROJ-021; metaform export takes no origin= and refuses it. Open: one export or two, section 08 question 5, and whether history units follow the import-does-nothing rule or keep both with the next suffix, question 13. PROJ-022, pending work travelling with continuation, is deferred. Task: Decide questions 5 and 13, then build the unit export and import.
- Serves: agent orchestrator `stakeholder.orchestrator.agent`

## test suite

- Address: `code.suite.test`
- Role: SE
- name_length: 2
- Ref path: tests
- Ref path: conftest.py
- Work record, tbd: QUAL-009 asks for orphans on both sides; the conftest check lists only tests without a requirement, not requirements that need a test and have none. QUAL-005: OPEN-QUESTIONS' engineering choice E3 is Ruff's defaults plus import sorting, bugbear and pyupgrade, with a reason required on each suppression, while pyproject.toml says the rule set is open and runs Ruff's defaults, so a suppression without a reason passes. E5 keeps the reviews under reviews/; they are in specifications/spec. QUAL-007's trigger is open. Task: Add the listing of requirements with no test; apply E3's rule set and the reasoned-suppression check, or decide section 07 question 1; decide where reviews live and what triggers the test-gaming review.
- Serves: specification `document.specification`

## help system

- Address: `code.system.help`
- Role: SE
- name_length: 2

## plugin system

- Address: `code.system.plugin`
- Role: SE
- name_length: 2
- Ref path: src/metaform/module.py
- Ref path: src/metaform/loader.py
- Ref path: src/metaform/module_metadata.py
- Ref path: src/metaform/modules
- Work record, tbd: BASE-027: at release Metaform offers to maintain a module author's fork of the template, its CI on three systems and the build of their wheel; the intent is confirmed and the behavior, service and commands are open, section 04 question 6. Also open: a per-project module place, question 1, and whether a module may call another module's operation beyond events, question 7. Task: Decide how fork, CI and wheel upkeep works and which commands carry it, then build it; decide questions 1 and 7.
- Serves: chassis `code.chassis`, module author `stakeholder.author.module`, mcp server `code.server.mcp`

## settings system

- Address: `code.system.settings`
- Role: SE
- name_length: 2
- Ref path: src/metaform/settings.py
- Ref path: src/metaform/tui.py
- Serves: chassis `code.chassis`, agent orchestrator `stakeholder.orchestrator.agent`

## module template

- Address: `code.template.module`
- Role: SE
- name_length: 2

## map viewer

- Address: `code.viewer.map`
- Role: SE
- name_length: 2
- Ref path: src/metaform/modules/web
- Work record, tbd: Specified and not built: serving web variants of a user's artifact side by side, each reconstructed and on its own port, which the web module is recommended to own, PROJ-019 and section 08 question 8. Open: how another module adds a view to this one GUI, VIEW question 3, and which folder's settings the GUI shows for a project, question 5, built as the project's registered folder until answered. Task: Decide which module serves variants and build PROJ-019; decide how a module adds a view.
- Serves: project owner `stakeholder.owner.project`

### map viewer receives from event bus

- Receiver: `code.viewer.map`
- Provider: `code.bus.event`
- Type: purpose
- Name: push of map.changed
- Purpose: Redraw every open page the moment a project's map changes, from the command line, over MCP or from another page, and send no request while nothing happens.
- Function: Delivers each map.changed to the web module's subscriber, which hands it to the running server in one loopback request carrying the server's nonce; the server writes it to every open page's event stream.
- EF: Function
- Relation: delivers each map.changed to the web module, which hands it to the running server for every open page
- Verb: delivers
- Observation: The web module subscribes with Subscription('map.changed', pushed). POST /api/notify is taken only from the loopback address with the X-Metaform-Nonce header from the server's run file, so a page cannot send it. With no server running the subscriber does nothing. A page reads once per event, and a burst that arrives during a read is read once more when it is done, VIEW-018.
- Non-goal: The page never polls and the server never pushes around the bus.
- Ref path: src/metaform/modules/web/__init__.py
- Ref spec: VIEW-018
- Ref spec: QUAL-015

### map viewer receives from graph store

- Receiver: `code.viewer.map`
- Provider: `code.store.graph`
- Type: purpose
- Name: reads through the data access object
- Purpose: Show a person exactly what agents are shown, no more and no less, so checking the map in the browser checks what agents receive.
- Function: Answers every read the page makes with the same store read the command line and the tools use, with the correction stack applied, the folder's or the page's layer choice as the starting selection, select and mask at each address, hidden layers left out and orphans shown only on a raw read.
- EF: Function
- Relation: answers each of the page's reads with the store read agents get, visibility applied inside it
- Verb: answers
- Observation: server.py maps /api/<read> one to one onto metaform query's reads, with project, metaform and layers picking the store and never passed as a read's argument; /api/graph pages the outer map with each element's nearest parent element and its joins with their subtypes; /api/layer-graph shows a building intake. The page computes no visibility of its own, VIEW-004.
- Ref path: src/metaform/modules/web/server.py
- Ref spec: VIEW-004

## transitive property

- Address: `data.property.transitive`
- Role: SE
- name_length: 2

## namespace tree

- Address: `data.tree.namespace`
- Role: SE
- name_length: 2
- Ref path: src/metaform/data/names.py
- Ref path: src/metaform/data/roots.json
- Serves: agent orchestrator `stakeholder.orchestrator.agent`

## agent definition

- Address: `document.definition.agent`
- Role: SE
- name_length: 2

## collaboration guide

- Address: `document.guide.collaboration`
- Role: SE
- name_length: 2

## extension guide

- Address: `document.guide.extension`
- Role: SE
- name_length: 2

## user guide

- Address: `document.guide.user`
- Role: SE
- name_length: 2
- Ref path: README.md
- Ref path: docs
- Work record, broken: Statements the current source contradicts: docs/guides/working-with-metaform.md line 234 says map knowledge does not expose the typed ef field, but op=add-join and op=add-subtype read ef and verb into their own fields, BASE-038. docs/preprint/inference-metaform.md lines 77, 316 and 368 and IMPLEMENTATION_MAP.md line 62 describe descriptor items holding an element's name, and IMPLEMENTATION_MAP.md lines 77 and 762 a missing flag; since step 49 an element is its address, name_length and role with the project's name on the join, and since step 42 conditions are tbd, broken or cruft work records. The set documents commit ce9062b while the code is at step 62. Task: Bring the guides, the technical reference and the preprint to the current source, or mark each passage as describing the ce9062b edition.
- Serves: project owner `stakeholder.owner.project`

## research paper

- Address: `document.paper.research`
- Role: SE
- name_length: 2

## intake procedure

- Address: `document.procedure.intake`
- Role: NE
- name_length: 2
- Ref path: specifications/Canonical_Intake.xml
- Ref path: src/metaform/modules/intake/resources/Canonical_Intake.xml
- Work record, tbd: The Canonical Intake names SE Substantial Element, line 20, while the spec's terms in 01-map.md, the preprint, docs/inference-metaform/REFERENCE.md and the repo-presentation agent call it Supportive Element; the project's one vocabulary has two names for one role. Task: Decide which name SE carries, in Rich's wording, and bring the spec and docs, or the intake text, to it.
- Serves: intake `code.intake`, specification `document.specification`

## build record

- Address: `document.record.build`
- Role: SE
- name_length: 2
- Work record, cruft: specifications/spec/HANDOFF.md still describes the build as it stood near step 11: the fix pass stopped partway with an uncommitted third step, Rich's CLAUDE.md edit uncommitted, and four open questions about the Canonical Intake, step 1's DET, a VE line, Subtype replaced by Vested Entity, and a missing nested subtype join, none of which the current text has. BUILD-LOG.md runs to step 62. Task: Rewrite HANDOFF.md from the build log's current state, or mark it superseded.

## decision record

- Address: `document.record.decision`
- Role: SE
- name_length: 2

## technical reference

- Address: `document.reference.technical`
- Role: SE
- name_length: 2

## agent skill

- Address: `document.skill.agent`
- Role: NE
- name_length: 2

## specification

- Address: `document.specification`
- Role: NE
- name_length: 1
- Ref path: specifications/spec
- Ref path: specifications/README.md
- Work record, cruft: Passages left from superseded designs: OPEN-QUESTIONS.md's Answered D8, D54 and D81 and CAPTURE's 09-25 entries describe one intake_submit submission after the whole method, replaced by recording one object per call, MAP-040. MAP-040 and BASE-039 say the Canonical Intake's schema still shows a name inside each element and tells the agent to remove absorbed subparts, and MAP-030 that it shows a provider beside the nested element and no non_goal; the current text has no element name, keeps absorbed elements, and gives the subtype join a non_goal and no provider. Task: Mark the superseded answers as superseded and bring MAP-030, MAP-040 and BASE-039's notes on the Canonical Intake's text to its current wording.
- Serves: agent orchestrator `stakeholder.orchestrator.agent`

### specification receives from intake procedure

- Receiver: `document.specification`
- Provider: `document.procedure.intake`
- Type: purpose
- Name: the proper schema
- Purpose: Take the map's shape, its concepts, roles, joins and subtype joins, from the one schema the intake follows, so the store and the tools hold exactly what an intake produces.
- Function: Gives the response schema, an element with namespace_address, name_length and role, a purpose join with provider, name, purpose, function, ef, relation, verb, observation, non_goal and refs, and a subtype join inside it holding its element, which the spec maps field by field onto the intake tools and the store's columns.
- EF: Function
- Relation: gives the map's shape in its response schema, which the spec maps field by field onto the tools and the store
- Verb: gives
- Observation: BUILD-BRIEF.md: the shape of the metaform comes from specifications/Canonical_Intake.xml, and where a record, older file or earlier code disagrees with its shape, it wins. MAP-040's table maps each XML field to its tool field and store column. The intake text is Rich's and changes only with his wording; a new text is adopted by copying it into the intake module's resources in the same commit.
- Ref path: specifications/spec/BUILD-BRIEF.md
- Ref spec: MAP-040

### specification receives from test suite

- Receiver: `document.specification`
- Provider: `code.suite.test`
- Type: purpose
- Name: tests
- Purpose: Have every requirement protected by a test that fails on a build that gets it wrong, and by nothing written for show, so a wrong build cannot pass as the design.
- Function: Holds tests written from the records before the code and seen failing first, each naming the requirement it protects and whether it is a fixture, a simulation or a real run, run against isolated homes through the real command line, the store and real MCP traffic, with a test-gaming review of every new or changed test.
- EF: Function
- Relation: fails whenever a build gets a requirement wrong, each test naming the requirement it protects
- Verb: fails
- Observation: tests/ holds 21 chassis test files with fakes.py, storekit.py and fixtures/intake_timer.json; each module keeps its tests in its own folder, and pytest collects tests and src/metaform/modules. conftest.py gives each test an isolated METAFORM_HOME, the real CLI as a subprocess, a registered project and a store. On this machine 564 tests outside the web module passed in 303 s; the web module's tests drive Chromium through Playwright. TEST-REVIEW 1 to 8 were run by an agent with the records and the tests and no implementation.
- Non-goal: A passing run is never taken as proof of quality; the code itself is judged against the standard by a critic.
- Ref path: tests
- Ref path: conftest.py
- Ref spec: QUAL-006
- Ref spec: QUAL-007

#### Subtype: traceability check

- Provider: `code.check.traceability`
- Name: requirement trace
- Function: Stops a test run when any collected test has no req marker naming a record of the spec, or no kind of fixture, simulation or real.
- EF: Function
- Relation: stops the test run when a test names no record of the spec or no kind of run
- Verb: stops
- Observation: conftest.py's pytest_collection_modifyitems reads the record ids from specifications/spec/0*.md and raises a UsageError listing each test without a traced requirement, QUAL-009, QUAL-014 and E4.
- Ref path: conftest.py
- Ref spec: QUAL-009
- Ref spec: QUAL-014

#### Subtype: continuous integration

- Provider: `code.integration.continuous`
- Name: checks
- Function: Runs strict pyright over src/metaform and the shipped modules, Ruff, and every test with a Chromium browser, on Linux, macOS and Windows under Python 3.11 and 3.14, for every push and pull request, each check reporting on its own.
- EF: Function
- Relation: runs type checks, lint and every test on three systems and two Pythons for each push
- Verb: runs
- Observation: .github/workflows/checks.yml installs with uv sync --extra dev and playwright install --with-deps chromium; a newer push to a branch cancels the older run. The template module carries its own copy of the workflow for forks, QUAL-003.
- Ref path: .github/workflows/checks.yml
- Ref path: src/metaform/modules/template/.github/workflows/checks.yml
- Ref spec: QUAL-003

## quality standard

- Address: `document.standard.quality`
- Role: NE
- name_length: 2

