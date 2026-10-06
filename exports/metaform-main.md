# The metaform of metaform

Metaform `main`, intake layer `intake-20260926T192840Z-f04016`, made by claude-opus-5-5 as intake agent. 19 elements, 33 joins, 26 subtypes.

## 1. The artifact

### Metaform

`code.graph.knowledge`, read as "knowledge graph code", is the artifact under examination.

**Who receives it and why.**

- **agent orchestrator**, as Function: Have every agent it hands work on a project start from that project's functional form, what each part is for, who receives it and how, instead of reconstructing it from the files each session.

## 2. Who it is for

### module author

`stakeholder.author.module`, read as "module author stakeholder", is a vested entity.

#### The package builder carries the module author's module inside the wheel.

module author receives from metaform build.

**Why.** Ship the module to others inside a Metaform wheel with the dependencies it declares.

**How (Function).** metaform build carries each loaded module as a system module of the wheel, names it as a metaform.modules entry point, and vendors its pure-Python DEPENDENCIES; a compiled one stays in Requires-Dist and the build names it with the module that needs it.

**Relation.** The package builder carries the module author's module inside the wheel.

**What is there.** Only modules that are on and loaded are carried, so helloworld and template, which ship disabled, are left out of a default build.

Sources: `src/metaform/build.py`

#### The plugin system lets a module author plug a capability into Metaform with one declaration.

module author receives from module contract and loader.

**Why.** Add a capability to Metaform as a module, declared once in its own folder, that runs as a metaform command and an MCP tool with its own settings, events, status line and lifecycle, without changing the chassis.

**How (Encounter).** The module contract takes one MODULE = Module(...) with verbs, nouns, settings declared in code, subscriptions, start, stop and a status hook, and from it the chassis builds the command, the tool, the help pages and the settings screen rows; the loader finds the module in the system place, the user place under the home or an installed entry point, and reads its SUPPORTED_OS, DEPENDENCIES and SHIPS_DISABLED without running it.

**Relation.** The plugin system lets a module author plug a capability into Metaform with one declaration.

**What is there.** A module is a folder with an __init__.py; its id must match the folder, its purpose must not be empty, and its tools are named <id>_<verb>. Chassis command names are reserved. metaform enable and disable turn a module on and off by name, and its settings keep their values while it is off. Every shipped module has a developer README in one layout.

Sources: `src/metaform/module.py`

- **template**, `code.template.module`, read as "module template code" (Encounter). The empty start of every module: every field helloworld declares, left empty, a README in the shipped layout, a CHANGELOG of each contract change so a copy can follow it, and its own CI workflow for three systems. The module template gives a module author a start that already follows the contract. What is there: Ships disabled. Copy the folder, rename it, set MODULE.id and the purpose, then metaform enable <id>. Sources: `src/metaform/modules/template`.
- **helloworld**, `code.module.example`, read as "example module code" (Encounter). Shows each chassis feature working once: a sync verb with a noun and a switch that publishes helloworld.greeted, an async verb, a caution verb, a verb for Windows only, settings declared in code including a select fed by its own data, a subscriber that keeps each greeted name as an item of its own layer, and a status line. The example module shows a module author every contract feature working. What is there: Ships disabled; its tests run with the suite. Sources: `src/metaform/modules/helloworld`.

### agent orchestrator

`stakeholder.orchestrator.agent`, read as "agent orchestrator stakeholder", is a vested entity.

#### The installer connects each AI tool to Metaform's MCP server and skill.

agent orchestrator receives from installer.

**Why.** Have every AI tool its agents run in start Metaform's server and find its skill, proven before setup says it is done, and removable again without touching anything else.

**How (Function).** metaform install checks the system first, previews every change with its backup, registers the uvx entry with each chosen tool through its own command or by merging one entry into its JSON config, copies the one skill to the shared folders and each tool's skill folder, then starts the exact registered command and proves it answers; metaform uninstall removes only what setup recorded and leaves the home's data.

**Relation.** The installer connects each AI tool to Metaform's MCP server and skill.

**What is there.** Claude Code, Codex, Gemini CLI, Cursor and VS Code are set up; Copilot CLI, Factory, Antigravity and Claude Desktop are listed as unverified and never set up. With no tool named it asks; naming tools or all sets up without asking. Setups are recorded in the installs table of the base database.

Sources: `src/metaform/install.py`, `src/metaform/probe.py`

- **server probe**, `code.probe.server`, read as "server probe code" (Function). Starts the registered command, sends initialize, the initialized notification and tools/list as newline-delimited JSON-RPC, and passes only when at least one tool comes back within the time limit; the server always stops. The server probe proves a registered tool can start the MCP server. What is there: probe.py is a small standard-library MCP client; standard error is kept only to show in a failure. Sources: `src/metaform/probe.py`.
- **skill load check**, `code.verifier.skill`, read as "skill verifier code" (Function). Shows, for each tool, that the tool itself loads the Metaform skill from the folder the installer writes. The skill verifier proves each skill folder is one the tool reads. What is there: Not built. MCP-022 is recommended, so built as written; the skill folder paths come from secondary sources and a skill in the wrong folder fails silently. Sources: `specifications/spec/06-mcp-install.md`. Finding: missing. MCP-022 has no verification per tool.

#### The intake module turns one subagent's run of the Canonical Intake into the project's stored functional map.

agent orchestrator receives from intake module.

**Why.** Have a subagent map the project's functionality once, from the artifact itself, and keep that map whole as the base every later layer builds on.

**How (Function).** The intake module serves the Canonical Intake with the project's target filled in, and stores the agent's final shape, submitted once, as one immutable intake layer in one atomic write, never refusing it for its content; a second intake goes into a new active metaform and the earlier one is kept whole.

**Relation.** The intake module turns one subagent's run of the Canonical Intake into the project's stored functional map.

**What is there.** Verbs prompt, submit and status, tools intake_prompt, intake_submit and intake_status. On the command line elements= names a JSON file or - for standard input; over MCP it is the array itself. The layer is named intake-<UTC time>-<6 hex>, kind intake, not hideable, created ready, with provenance module intake, workflow canonical-intake, no copy of the prompt text, and the model, role and blinded flag the agent gives. The status hook prints 'Intake: complete' and 'Start with: metaform map roots' once there is one.

Sources: `src/metaform/modules/intake`

- **Canonical Intake**, `document.procedure.intake`, read as "intake procedure document" (Encounter). Instructs the performing agent through the Digital Typology method: the vested entity rules, the namespace rules with valid and invalid examples, the steps from surveying every member to annealing, and the response schema with ef, nested subtype joins and refs. The Canonical Intake tells the intake agent how to find the VE, the DE, the joins and the namespace of the artifact it examines. What is there: It is served unchanged except the target element's type and value and any {project_id} placeholder, followed by the submit lines: always the submit and stop-and-report rule, the report request while --report is on, the feedback request while --debug is on. The copy in specifications and the module resource are byte copies; a test fails when they differ. Sources: `specifications/Canonical_Intake.xml`, `src/metaform/modules/intake/resources/Canonical_Intake.xml`.
- **submission writer**, `code.writer.submission`, read as "submission writer code" (Function). Writes each element, join and subtype of the submission through the data access object, stores a missing field empty, keeps unknown fields and a subtype purpose in extra, stores a provider that names no element as a new element, and names every such case with its path in the submission, such as elements[3].joins[0].ef. The submission writer stores whatever the intake agent sends and says where it did not fit. What is there: The input schema takes namespace_address, role, name, name_length, refs, flag, flag_note and joins; a join takes provider, purpose, function, ef, relation, observation, non_goal, refs and subtypes; a subtype takes provider, function, ef, relation, observation and element. Only elements that cannot be read at all store nothing, with one notice to save the shape through feedback. Sources: `src/metaform/modules/intake/submission.py`, `src/metaform/modules/intake/schema.py`.

#### The package builder makes the one wheel Metaform runs from and is registered from.

agent orchestrator receives from metaform build.

**Why.** Run Metaform with exactly the modules it has enabled from one file, on a machine or in a hosted code environment with nothing installed, and keep that run's data apart until it is pulled in.

**How (Function).** metaform build writes one wheel from the installed package: the chassis, each loaded module as a system module without its tests, every pure-Python dependency under metaform/_vendor/, and a root __main__.py so python <wheel> runs it directly with its home at ~/.metaform/wheels/<name>-<version>; a compiled dependency stays in Requires-Dist and the build names the module that needs it.

**Relation.** The package builder makes the one wheel Metaform runs from and is registered from.

**What is there.** The wheel goes to builds/<UTC time>/ in the home and is recorded as last_build. The build needs uv to resolve dependencies. _build_info.py copies the chassis dependencies for the built wheel, and a test fails when they differ from pyproject.toml. metaform import wheel=<name>-<version> pulls a directly run wheel's metaforms in as their own, never active, once.

Sources: `src/metaform/build.py`, `src/metaform/_build_info.py`

#### The chassis serves the orchestrator's agents their project's functional map through every module verb.

agent orchestrator receives from chassis.

**Why.** Give each agent its project's map, its place in it and exactly the knowledge in scope for its task, from whatever folder and AI tool the agent works in.

**How (Function).** The chassis keeps every registered project's metaforms in the home, resolves each call's project and toggled layers from the folder it runs in or the call itself, and runs each module verb with one Context, so the map reads the same way as a metaform command and as an MCP tool.

**Relation.** The chassis serves the orchestrator's agents their project's functional map through every module verb.

**What is there.** The chassis runs on its own as a CLI and MCP is a module. metaform with no words prints the home, the folder's project and target, the active metaform, the modules loaded and each module's status line, such as 'Intake: none yet' with the notice to delegate the intake to a subagent.

**Not sought.** The chassis runs no workflows; the orchestrator hands work by name and modules do the work.

Sources: `src/metaform/cli.py`, `src/metaform/context.py`, `src/metaform/module.py`

#### The MCP server brings Metaform's verbs into each agent's AI tool.

agent orchestrator receives from MCP module.

**Why.** Let agents in any AI tool reach every Metaform command as a tool, with the same checks and the same next steps as the command line.

**How (Encounter).** The mcp module runs the official SDK's low-level server over stdio for the folder it starts in; every verb of a module on the surface becomes the tool <module>_<verb>, recomputed on each request, beside the chassis tools set, feedback, list_reports and read_report, which narrowing never hides, and the history and prompt tools while the chassis is on the surface.

**Relation.** The MCP server brings Metaform's verbs into each agent's AI tool.

**What is there.** A host starts it with uvx --from <wheel> metaform mcp serve. Every tool takes an optional project and layers for one call, and a caution verb takes confirm. A coroutine verb is awaited in the server loop and a plain one runs in a worker thread. A result is one text block of say lines when there are any, then one block holding the result.

Sources: `src/metaform/modules/mcp`

#### The feedback channel keeps agents' trouble reports, intake reports and process feedback where the orchestrator reviews them.

agent orchestrator receives from feedback and reports.

**Why.** Have an agent that cannot continue stop and leave what it has with a trouble report instead of retrying, and keep every intake's report and process feedback beside the layer it made for review.

**How (Function).** The feedback verb and tool save feedback text, a report and a shape as files under the home's projects/<id>/reports/, each with a row in the active metaform's reports table and linked to a layer when one is named; a second write for the same run appends a timestamped section under a file lock; list reports and read report give them back exactly; nothing given is refused.

**Relation.** The feedback channel keeps agents' trouble reports, intake reports and process feedback where the orchestrator reviews them.

**What is there.** Files are named <run id>-report.md, <run id>-feedback.md or <run id>-shape.txt. feedback, list_reports and read_report stay on every MCP surface and always run on the CLI, whatever --modules narrows. --debug, off by default, asks agents for process feedback; --report, on by default, asks the intake agent for a report on the project.

Sources: `src/metaform/reports.py`

#### Metaform gives the agent orchestrator a stored functional map of each project that its agents read before they change anything.

agent orchestrator receives from Metaform.

**Why.** Have every agent it hands work on a project start from that project's functional form, what each part is for, who receives it and how, instead of reconstructing it from the files each session.

**How (Function).** Metaform registers any artifact as a project, has a subagent map its functionality once into a metaform kept in the Metaform home, and serves that map with its correction, knowledge and memory layers to agents as metaform commands and MCP tools, and to people in a web GUI.

**Relation.** Metaform gives the agent orchestrator a stored functional map of each project that its agents read before they change anything.

**What is there.** The repository holds the chassis package src/metaform with seven shipped modules, intake, map, memory, mcp and web on, helloworld and template off; 482 tests with CI on three systems; and the specification the build follows. It is a Python 3.11 package whose one runtime dependency is prompt_toolkit, and the mcp module adds the mcp package. All data lives under ~/.metaform or METAFORM_HOME, never in a project folder.

**Not sought.** It does not map the implementation: no AST, call graph, class tree or file layout becomes the map's shape.

Sources: `src/metaform`, `tests`, `conftest.py`, `pyproject.toml`, `.github/workflows/checks.yml`, `specifications`, `README.md`, `CLAUDE.md`

#### Variant history keeps every worker's result as a sibling variant of one origin.

agent orchestrator receives from origins and variants.

**Why.** Collect each worker's output, committed or not, against one baseline, and rebuild any of those outputs later, anywhere.

**How (Function).** History establishes an origin from the project's current state, a repository's commit or a full copy of a plain folder, collects a folder such as a worker's worktree as a variant stored as only the files that differ from its origin, and extracts any variant, several or all into folders with Python alone, checking every file's hash.

**Relation.** Variant history keeps every worker's result as a sibling variant of one origin.

**What is there.** metaform add origin, list origins, add variant, list variants and extract, and the same five as MCP tools. The boundary is git ls-files --cached --others --exclude-standard in a repository, so untracked files git does not ignore belong to it. Changed text is stored whole under 3 MB and as a git diff at or above it. Rows live in the project's history.sqlite3 and payloads under origins/ in the home. A repository's uncommitted work is collected at once as variant v000001. remove=true removes a git worktree only after its variant reconstructs what it held.

Sources: `src/metaform/data/history.py`

- **web variants side by side**, `code.launcher.variant`, read as "variant launcher code" (Function). Launches variants of a web artifact together, each served on its own port, so they open side by side in browser tabs. The variant launcher lets the orchestrator compare web variants of one origin side by side. What is there: Not built. PROJ-019 is confirmed as wanted; its owning module and port choice are open question 8 of section 08. Sources: `specifications/spec/08-projects.md`. Finding: missing. PROJ-019 is confirmed and not built.
- **origin unit export**, `code.export.origin`, read as "origin export code" (Function). Exports a whole origin unit, the origin and every variant pinned to it, as a wheel whose own CLI reconstructs any of its variants, and imports such a unit without losing local data. The origin export carries a whole history unit to another machine. What is there: Not built. PROJ-020 is confirmed; how it relates to project export, and whether PROJ-021 or STORE-027's import rule governs units, are open questions 5 and 13 of section 08. Sources: `specifications/spec/08-projects.md`. Finding: missing. PROJ-020 and PROJ-021 are not built, waiting on section 08 questions 5 and 13.

#### The agent instructions tell each arriving agent how to work from the map.

agent orchestrator receives from agent instructions.

**Why.** Have every agent that enters a project learn what Metaform keeps there, what each enabled module is for, and the one next step, such as delegating the intake, without anyone briefing it.

**How (Encounter).** The agent instructions are composed live from the chassis base text, the stop-and-report rule, the feedback request while --debug is on, each surfaced module's purpose under its id, and each module's status notice, or the way to register a project when the folder has none; the same text is metaform help agents and the MCP server's instructions.

**Relation.** The agent instructions tell each arriving agent how to work from the map.

**What is there.** instructions.py composes the text and names no module itself; the skill is the fixed pointer to it that the installer copies into each tool.

Sources: `src/metaform/instructions.py`

- **Metaform skill**, `document.skill.agent`, read as "agent skill document" (Encounter). Tells an agent working in a registered project, or one that hears of Metaform or a functional map, to run metaform in the project folder and metaform help agents, and to follow the next step Metaform gives. The skill sends an agent in any AI tool to the live instructions. What is there: skill/SKILL.md, eight lines; enabling a module changes no skill file. Sources: `src/metaform/skill/SKILL.md`.

#### Agent memory keeps what agents noted at each node of the map for every later agent.

agent orchestrator receives from memory module.

**Why.** When the map is wrong or incomplete at a place, have the agent that finds out leave a note there, so the next agent reads it where it looks.

**How (Function).** The memory module offers the MCP reference memory server's nine operations over the map's own nodes: an observation is an item of the one memory layer at an element, join or subtype, and a relation is an item at its from node linking to its to node.

**Relation.** Agent memory keeps what agents noted at each node of the map for every later agent.

**What is there.** Verbs create-entities, create-relations, add-observations, delete-entities, delete-observations, delete-relations, read-graph, search-nodes and open-nodes. Nodes are written element:<address or id>, join:<id> or subtype:<address or id>.

**Not sought.** Memory belongs to no single agent and keeps no history of its changes.

Sources: `src/metaform/modules/memory`

#### The map API puts the functional map and its layers in agents' hands as verbs.

agent orchestrator receives from map module.

**Why.** Have agents read the purpose of a part before they change it, and record what they learn as knowledge and correction layers on the same map.

**How (Encounter).** The map module turns each data access object read and write into a verb and an MCP tool: roots as the map's entry, where, element, joins, identity, subtypes, children, node, context, links, citing, history, stack, search and findings; knowledge to build layers; tag, untag, select, mask, clear, hide, unhide and reexamined for layers; add-metaform and activate; answer and approve for blind-spot challenges.

**Relation.** The map API puts the functional map and its layers in agents' hands as verbs.

**What is there.** 31 verbs, tools map_<verb>. --raw reads every stored layer, building, hidden and masked ones included. approve runs on the CLI only, where a person acts, and hide needs --confirm. Every join read shows the layer it comes from and every object its flag.

Sources: `src/metaform/modules/map`

- **knowledge tool**, `code.tool.knowledge`, read as "knowledge tool code" (Function). One read-write verb, the only one that makes a new layer: op=create, add-element, add-join, add-subtype, add-property, add-item, add-ref, add-plan, edit, remove, correct, finish, peel and discard, each call naming its layer. The knowledge tool builds knowledge and correction layers one object per call. What is there: An add sent without layer= goes to a new building layer unnamed-<UTC time> with a notice. A noun an op does not read goes to the new record's extra with a notice. It has no ef noun. Sources: `src/metaform/modules/map/__init__.py`. Finding: missing. map knowledge takes no ef noun, so joins and subtypes a knowledge layer adds, and corrections made through the tool, cannot carry the Function or Encounter word MAP-020 gives every join; an ef= given goes to extra.

#### The web GUI shows the orchestrator every project's map and its layers.

agent orchestrator receives from web GUI.

**Why.** See each project's functional map, its layers, provenance, prompts and corrections in a browser, and change only what the orchestrator chooses to change there.

**How (Encounter).** The web module starts one detached server per home on one fixed port that serves every registered project: a 3D graph that draws each join as receiver to purpose to provider, a 2D map in the left window, an inspector with Object, Provenance, Prompt and Corrections tabs, and exactly three writes: apply the chosen layers to the project folder, save an edited prompt as a new version, and peel and discard the top correction layer.

**Relation.** The web GUI shows the orchestrator every project's map and its layers.

**What is there.** metaform web starts it or prints the address it already runs at, by default http://127.0.0.1:7433/, and metaform web stop ends it. Every request must name the server in its Host header; a bind address other than loopback also needs the home's token. 3d-force-graph, Mermaid, CodeMirror 5 and IBM Plex are bundled under vendor/ with their licenses, so it works offline. While --web-autostart is on, agents are told to start it after an intake and give the user its address.

Sources: `src/metaform/modules/web`

- **web GUI server**, `code.server.web`, read as "web server code" (Function). The standard library's threading HTTP server, detached from the terminal, answers /api/<read> with one data access object read by its query name, the prompt reads, and the three POST writes from the page's own origin with a JSON body. The web server carries the GUI between the browser and the home. What is there: server.py records pid, bind, port, home and nonce in run/web.json, writes only failures to run/web.log, and binds without the reverse lookup that stalled it on macOS. Sources: `src/metaform/modules/web/server.py`.
- **viewer**, `code.viewer.graph`, read as "graph viewer code" (Encounter). Floats the metaform in 3D with vertices colored by kind, links by layer, and encounter links teal for Function and magenta for Encounter; lays the whole map out in 2D with Mermaid; both views select together, the camera flies to the selected object, arrow keys follow joins and F fits the map. The viewer shows the map in its receiver, purpose and encounter form. What is there: page/index.html, app.js and app.css, with pause and re-run layout controls; particles and camera flights stop under reduced motion. Sources: `src/metaform/modules/web/page`.
- **prompt editor**, `code.editor.prompt`, read as "prompt editor code" (Encounter). Edits a stored prompt in CodeMirror with XML and Markdown modes, shows the diff against the version the text came from, saves it as the next version without changing any version, and names the layers each version made. The prompt editor lets the orchestrator improve a prompt while every layer keeps the version it was made from. What is there: Nothing fills the home's prompt store yet: the Canonical Intake is never stored and no module ships a prompt, so the Prompt tab shows 'No stored prompts yet'. Sources: `src/metaform/modules/web/page/app.js`.

#### The specification is the contract the orchestrator's building agents build Metaform from.

agent orchestrator receives from Metaform specification.

**Why.** Hand every agent building Metaform one current contract to build from, with the reason for each requirement and the tests that protect it, so the build serves the design and not an agent's guess.

**How (Encounter).** The specification, sections 01 to 09 of about 230 records, gives each requirement its meaning, the reason from the design, observable behavior, build detail, acceptance tests, relations and status, and wins over any other document, code or test; OPEN-QUESTIONS.md merges the open questions, TRACE.md maps every source requirement, and BUILD-LOG.md, the reviews and the manual tests record the build.

**Relation.** The specification is the contract the orchestrator's building agents build Metaform from.

**What is there.** specifications/spec/00-index.md is the entry, with a scope freeze for the first release and the build order. HANDOFF.md still describes the state before build steps 12 to 27 while BUILD-LOG.md runs to step 27. Canonical_Intake_old.xml and Canonical_Intake_test.xml are reference copies, the test copy without ef, and Sonnet_Intake.xml is a reference intake result.

Sources: `specifications/spec`, `specifications/REQUIREMENTS.md`, `specifications/REQUIREMENTS-corrections.md`, `specifications/SETTLED.md`, `specifications/code_quality_standards.md`, `specifications/metaprompting_element_segments_example.md`, `specifications/README.md`

- **CLAUDE.md**, `document.rules.collaboration`, read as "collaboration rules document" (Encounter). States how an agent works on Metaform with Rich: no gates on prompted outputs unless they guard a named silent failure, intent encoded exactly as given, Linux, macOS and Windows for everything, turns that keep moving, and the MetaformFoundation block for expert agents building the platform. The collaboration rules govern how building agents work while they build from the specification. What is there: It says its instructions are for agents developing Metaform, never for agents in the runtime. Sources: `CLAUDE.md`.

## 3. What defines it

### chassis

`code.chassis`, read as "chassis code", is the defining element.

**Who receives it and why.**

- **agent orchestrator**, as Function: Give each agent its project's map, its place in it and exactly the knowledge in scope for its task, from whatever folder and AI tool the agent works in.

#### The plugin system loads the modules the chassis runs.

chassis receives from module contract and loader.

**Why.** Carry every capability beyond its own commands as modules it finds, checks and loads on its own, and withdraw everything a module registered when it goes.

**How (Function).** The loader discovers modules in the system place, the user place and entry points, reads each declaration before any of its code runs, reports a module that is off, on an unsupported system, missing a dependency or failing to import without stopping, loads the enabled ones with the settings they declare owned by them, calls start, and on unload cancels their tasks, calls stop and withdraws their settings while stored data stays.

**Relation.** The plugin system loads the modules the chassis runs.

**What is there.** metaform list modules shows each module on, off or error, where it was found and why it did not load. An id held by an earlier place does not load again from a later one. Modules reach each other only through events.

Sources: `src/metaform/loader.py`, `src/metaform/module_metadata.py`, `src/metaform/events.py`

- **declaration reader**, `code.parser.declaration`, read as "declaration parser code" (Function). Reads SUPPORTED_OS, DEPENDENCIES, SHIPS_DISABLED, REQUIRES_CHASSIS and the summary as top-level literals of __init__.py and manifest.py with ast, never executing them. The declaration parser tells the loader whether a module fits this system before its code runs. What is there: module_metadata.py; a name assigned twice or to a non-literal is an error naming the declaration. Sources: `src/metaform/module_metadata.py`.
- **event bus**, `code.bus.event`, read as "event bus code" (Function). Delivers a published topic to every loaded subscriber with its own Context and a copy of the payload, and returns each delivery's outcome, completed, failed or cancelled, to the publisher; one subscriber's failure never hides another's. The event bus connects modules without either naming the other. What is there: events.py; from inside a running loop async subscribers are awaited and sync ones run in a worker thread. The bus runs no workflow. Only helloworld subscribes today. Sources: `src/metaform/events.py`.

#### The command line interface is how people and agents drive the chassis and every module.

chassis receives from metaform command line.

**Why.** Run every chassis command and module verb the same way, with every switch a setting declared once, help drawn from the live declarations, and every error ending in the one command to run next.

**How (Encounter).** The command line reads the first word as a chassis verb or a module id, takes required nouns in order, optional nouns as name=value and switches as settings, --name, --no-name, --name value or a one-letter form, stops parsing at --, runs the verb with its own Context, prints its result as text or --json, and on a user error prints one Error line and one Next line.

**Relation.** The command line interface is how people and agents drive the chassis and every module.

**What is there.** Twenty chassis verbs: help, add, list, set, unset, config, enable, disable, activate, import, export, query, install, uninstall, build, feedback, read, extract, prompts and prompt. A setting is default, set or glued, and applies to its folder and every folder below it; defaults are never written. --modules narrows the folder's command surface and says how to restore it. A caution verb needs --confirm. Exit codes are 2 for a user error, 1 for a failure, 3 for a cancel and 130 for an interrupt.

Sources: `src/metaform/cli.py`, `src/metaform/grammar.py`, `src/metaform/docs.py`, `src/metaform/results.py`, `src/metaform/errors.py`

- **settings screen**, `code.screen.settings`, read as "settings screen code" (Encounter). A keyboard-driven screen that lists the chassis and each module with its settings, stages changes and saves them through the settings schema. The settings screen lets a person change settings without writing switches. What is there: tui.py on prompt_toolkit; metaform config opens it in a terminal, and config --show prints the settings instead. Sources: `src/metaform/tui.py`.
- **settings**, `code.schema.settings`, read as "settings schema code" (Function). One schema, filled by the chassis and by each module's declarations in code, drives parsing, checks, defaults, help, config --show, the settings screen and each tool's JSON types; values are stored per folder, or once for the home, with their glue. The settings schema makes each working folder's context, project, layers and command surface, out of ordinary settings. What is there: settings.py. Chassis settings are project, modules, layers, debug and report; --project stops at a registered project's own folder; a name in --layers that is no layer or tag is kept with a notice. Sources: `src/metaform/settings.py`.
- **query**, `code.interface.query`, read as "query interface code" (Encounter). metaform query runs one of 25 named reads of the data access object with positional arguments and name=value options, and no general SQL; the web GUI calls the same reads by name. The query interface asks the design's own questions of a project on the command line. What is there: query.py; metaform query alone lists the reads. Sources: `src/metaform/query.py`.

#### The graph store holds the metaform the chassis serves.

chassis receives from data access object and metaform store.

**Why.** Keep every registered project's metaforms in the Metaform home, never in a project folder, and let modules reach them only through one door that applies the same visibility rules on every read.

**How (Function).** The data access object, Store, is the only code that opens a store or issues SQL: one SQLite store per metaform, one row per thing, every write one transaction that never refuses content and names what did not fit in notices, every read one indexed read, in context where select, mask, hiding and building are resolved for each address, or raw on request.

**Relation.** The graph store holds the metaform the chassis serves.

**What is there.** Tables hold types, elements, joins with receiver, provider, purpose, function, ef, relation, observation and non_goal, subtypes, refs, layers of kind intake, layer, memory and correction, items with full-text search, properties, selections, provenance, findings, challenge states, plans and reports. An element is only an identity and an address; its name, name_length, role and refs are a descriptor item. A store lives at projects/<project>/metaforms/<id>/store.sqlite3 in the home, at schema version 1, and a store of an unknown version is refused before any write.

Sources: `src/metaform/data`, `src/metaform/sqlite.py`

- **challenge states and plans**, `code.tracker.challenge`, read as "challenge tracker code" (Function). Keeps each blind-spot challenge's answer A, B or C beside the critic's layer, never as an edit to it, and turns a B answer a person approves into a plan with its element and join. The challenge tracker records how the project answered a blind-spot critic. What is there: challenges.py; no module produces a blind-spot layer yet, since producing knowledge layers is module work waiting on D44. Sources: `src/metaform/data/challenges.py`.
- **correction stack**, `code.stack.correction`, read as "correction stack code" (Function). Applies finished correction layers in order on top of the intake map, the only way to remove, relocate or permanently add something to the metaform, keeps the current tables equal to the intake with the whole stack applied, marks every layer built on a changed thing for re-examination, and peels only the top layer. The correction stack is how the metaform changes after its intake. What is there: corrections.py. A relocation keeps the element id and its items and removes its joins; what a removal leaves pointing at nothing is kept, orphaned and not shown. Sources: `src/metaform/data/corrections.py`.
- **export and import**, `code.exchange.data`, read as "data exchange code" (Function). Writes named projects, or all, to one JSON document where every row carries its identity id and layer id, and imports only what the target home does not hold, checking the whole document first and writing each metaform in one transaction; pulls a directly run wheel's data in as its own metaforms, never active. Data exchange carries metaforms whole between homes by unique id. What is there: exchange.py; metaform export and import. Importing something that exists does nothing. Sources: `src/metaform/data/exchange.py`.
- **project registry**, `code.registry.project`, read as "project registry code" (Function). The home's base database registers each project with its folder and target, one of path, url, artifact, inline or inferred, records its metaforms and the active one, making main on the first write, and holds per-folder settings with their glue, each module on or off, and what setup installed. The project registry tells the chassis which project a folder works on and which metaform is active. What is there: home.py and context.py: a folder's project is the deepest registered project containing it unless --project names another; a folder another project holds is refused by name. Sources: `src/metaform/home.py`, `src/metaform/context.py`.
- **prompt store**, `code.store.prompt`, read as "prompt store code" (Function). Keeps prompts as versioned records in the home's prompts.sqlite3, each saved edit a new version with its parent and no version ever changed, and links each layer to the exact version it was made from. The prompt store lets a layer's provenance name the exact prompt text behind it. What is there: prompts.py; shipped() has no caller, so in a live home the store is empty until a module ships a prompt. metaform prompts and prompt read it. Sources: `src/metaform/data/prompts.py`.
- **layer selection**, `code.resolver.layer`, read as "layer resolver code" (Function). Computes the layers that reach each address as incoming and mask, or select, walked from trunk to leaf and starting from the folder's toggled layers, then removes hidden layers and every layer built from one; correction layers always apply and building layers never reach a read. The layer resolver decides which knowledge each agent receives at each place. What is there: selection.py; every read in context goes through one Resolver, so no path lets an excluded layer through. Sources: `src/metaform/data/selection.py`.

## 4. Its parts, in the order the trace reaches them

### metaform build

`code.builder.package`, read as "package builder code", is a supportive element.

**Who receives it and why.**

- **installer**, as Function: Register a wheel that holds the Metaform the user runs now.
- **module author**, as Function: Ship the module to others inside a Metaform wheel with the dependencies it declares.
- **agent orchestrator**, as Function: Run Metaform with exactly the modules it has enabled from one file, on a machine or in a hosted code environment with nothing installed, and keep that run's data apart until it is pulled in.

#### The plugin system tells the package builder what the wheel carries.

metaform build receives from module contract and loader.

**Why.** Carry exactly the modules that are loaded, each with what it declares it needs.

**How (Function).** The plugin system's discovery names the loaded modules, their folders and their DEPENDENCIES, which the build copies in as system modules and resolves with uv.

**Relation.** The plugin system tells the package builder what the wheel carries.

**What is there.** A module's tests folder is left out of the wheel.

Sources: `src/metaform/build.py`

### module contract and loader

`code.system.plugin`, read as "plugin system code", is a supportive element.

**Who receives it and why.**

- **metaform build**, as Function: Carry exactly the modules that are loaded, each with what it declares it needs.
- **chassis**, as Function: Carry every capability beyond its own commands as modules it finds, checks and loads on its own, and withdraw everything a module registered when it goes.
- **metaform command line**, as Function: Parse and run each module verb from its one declaration, with the settings it reads as its switches and its help page drawn from that declaration.
- **MCP module**, as Function: Serve exactly the tools of the modules on the folder's command surface, as they are declared now.
- **agent instructions**, as Function: Say what each enabled module is for, and add its current notice, without the chassis naming any module.
- **module author**, as Encounter: Add a capability to Metaform as a module, declared once in its own folder, that runs as a metaform command and an MCP tool with its own settings, events, status line and lifecycle, without changing the chassis.

### installer

`code.installer`, read as "installer code", is a supportive element.

**Who receives it and why.**

- **agent orchestrator**, as Function: Have every AI tool its agents run in start Metaform's server and find its skill, proven before setup says it is done, and removable again without touching anything else.

#### The MCP server's answer is the installer's proof.

installer receives from MCP module.

**Why.** Prove each registered tool can start Metaform's server before setup says it is done.

**How (Function).** The MCP server, started by the exact registered command, answers initialize and tools/list with at least one tool.

**Relation.** The MCP server's answer is the installer's proof.

**What is there.** A failed proof ends setup with exit 1 and the report printed.

Sources: `src/metaform/install.py`, `src/metaform/probe.py`

#### The package builder supplies the wheel the installer registers.

installer receives from metaform build.

**Why.** Register a wheel that holds the Metaform the user runs now.

**How (Function).** The installer takes the running wheel, or else the last wheel metaform build wrote, and registers uvx --from <wheel> metaform mcp serve.

**Relation.** The package builder supplies the wheel the installer registers.

**What is there.** With no wheel yet, install stops with the next step metaform build.

Sources: `src/metaform/install.py`

### intake module

`code.intake`, read as "intake code", is a supportive element.

**Who receives it and why.**

- **agent orchestrator**, as Function: Have a subagent map the project's functionality once, from the artifact itself, and keep that map whole as the base every later layer builds on.

#### The feedback channel keeps the intake's report and feedback beside its layer.

intake module receives from feedback and reports.

**Why.** Keep the intake agent's report on the project and its process feedback as provenance of the intake layer.

**How (Function).** save_report writes the report= and feedback= texts as the layer's report and feedback files, each with a row linked to the layer.

**Relation.** The feedback channel keeps the intake's report and feedback beside its layer.

**What is there.** The layer's provenance read lists them as refs, and the web GUI's Provenance tab lists their file names; read report gives their text.

Sources: `src/metaform/modules/intake/__init__.py`, `src/metaform/reports.py`

#### The graph store keeps the intake's map as the metaform's base layer.

intake module receives from data access object and metaform store.

**Why.** Store the whole submission as one intake layer that nothing edits afterward, and never lose an earlier intake.

**How (Function).** Store.atomic wraps the layer's creation with its provenance and every element, join, subtype and ref write, so the intake layer exists whole or not at all; into a metaform that already has an intake it writes a new metaform named intake-<UTC time>, withdrawn if the write fails, and makes it active.

**Relation.** The graph store keeps the intake's map as the metaform's base layer.

**What is there.** The result returns the layer, project, metaform, the counts of elements, joins, subtypes, refs and findings, and every notice with its path.

Sources: `src/metaform/modules/intake/__init__.py`

### MCP module

`code.server.mcp`, read as "mcp server code", is a supportive element.

**Who receives it and why.**

- **installer**, as Function: Prove each registered tool can start Metaform's server before setup says it is done.
- **agent orchestrator**, as Encounter: Let agents in any AI tool reach every Metaform command as a tool, with the same checks and the same next steps as the command line.

#### The plugin system supplies the MCP server's tool list.

MCP module receives from module contract and loader.

**Why.** Serve exactly the tools of the modules on the folder's command surface, as they are declared now.

**How (Function).** The plugin system gives the server every loaded module on the surface, and each verb declared for MCP and this system becomes a tool whose input schema comes from its nouns, the settings it reads, confirm for a caution verb, project and layers.

**Relation.** The plugin system supplies the MCP server's tool list.

**What is there.** The list is rebuilt on every tools/list request, so enabling a module or narrowing --modules changes what the next request sees.

Sources: `src/metaform/modules/mcp/server.py`

#### The command grammar checks every tool call the MCP server receives.

MCP module receives from metaform command line.

**Why.** Check each tool call's arguments exactly as the command line would, and fail with the command line's next step.

**How (Function).** The command grammar checks each required noun and each value's kind, checks switch values as set does, and keeps a name the verb does not know in the record's extra with a notice, or ignores it with one.

**Relation.** The command grammar checks every tool call the MCP server receives.

**What is there.** A tool error comes back marked as an error with one Error line and one Next line.

Sources: `src/metaform/grammar.py`, `src/metaform/modules/mcp/server.py`

#### The agent instructions reach an MCP host when it connects.

MCP module receives from agent instructions.

**Why.** Give the host's agent Metaform's instructions when it connects.

**How (Encounter).** The instructions composed for the server's folder become the server's instructions at initialize.

**Relation.** The agent instructions reach an MCP host when it connects.

**What is there.** They are composed once, when the server starts; the tool list is recomputed per request and the instructions are not, so a notice such as the one to delegate the intake stays until the host reconnects.

Sources: `src/metaform/modules/mcp/server.py`

### feedback and reports

`code.channel.feedback`, read as "feedback channel code", is a supportive element.

**Who receives it and why.**

- **intake module**, as Function: Keep the intake agent's report on the project and its process feedback as provenance of the intake layer.
- **agent orchestrator**, as Function: Have an agent that cannot continue stop and leave what it has with a trouble report instead of retrying, and keep every intake's report and process feedback beside the layer it made for review.

### origins and variants

`code.history.variant`, read as "variant history code", is a supportive element.

**Who receives it and why.**

- **agent orchestrator**, as Function: Collect each worker's output, committed or not, against one baseline, and rebuild any of those outputs later, anywhere.

### agent instructions

`document.instructions.agent`, read as "agent instructions document", is a supportive element.

**Who receives it and why.**

- **MCP module**, as Encounter: Give the host's agent Metaform's instructions when it connects.
- **agent orchestrator**, as Encounter: Have every agent that enters a project learn what Metaform keeps there, what each enabled module is for, and the one next step, such as delegating the intake, without anyone briefing it.

#### The plugin system gives the agent instructions each module's purpose and notice.

agent instructions receives from module contract and loader.

**Why.** Say what each enabled module is for, and add its current notice, without the chassis naming any module.

**How (Function).** Each surfaced module's purpose goes under its id in module id order, then each status hook's notice for the folder's project; a failing hook adds nothing.

**Relation.** The plugin system gives the agent instructions each module's purpose and notice.

**What is there.** The intake notice to delegate the intake and the web notice to start the GUI after an intake both arrive this way.

Sources: `src/metaform/instructions.py`

### memory module

`code.memory.agent`, read as "agent memory code", is a supportive element.

**Who receives it and why.**

- **agent orchestrator**, as Function: When the map is wrong or incomplete at a place, have the agent that finds out leave a note there, so the next agent reads it where it looks.

#### The graph store holds agent memory at the map's nodes.

memory module receives from data access object and metaform store.

**Why.** Keep each observation and relation at the map's own node in one memory layer that follows the same visibility rules as every layer.

**How (Function).** The store makes the memory layer, kind memory, mutable, hideable and without provenance, on the first write; holds each observation as an item at its node and each relation as an item linking to its to node; changes and deletes memory in place; and finds nodes by full-text search of item values.

**Relation.** The graph store holds agent memory at the map's nodes.

**What is there.** read-graph, search-nodes and open-nodes read memory in context, so hiding or masking the memory layer hides it there too; create-entities adds an element in the memory layer at an address the map does not hold.

Sources: `src/metaform/modules/memory/__init__.py`

### map module

`code.api.map`, read as "map api code", is a supportive element.

**Who receives it and why.**

- **agent orchestrator**, as Encounter: Have agents read the purpose of a part before they change it, and record what they learn as knowledge and correction layers on the same map.

#### The graph store answers each map verb.

map module receives from data access object and metaform store.

**Why.** Answer every map verb with exactly one data access object operation, so an agent reads what the store's rules let it see and writes only through them.

**How (Function).** Each verb calls one read or write of the Store, in context with the folder's or the call's toggled layers unless --raw, and returns the record with the store's notices.

**Relation.** The graph store answers each map verb.

**What is there.** With no project for the folder, every verb stops with the next step to register or select one.

Sources: `src/metaform/modules/map/__init__.py`

### web GUI

`code.gui.web`, read as "web gui code", is a supportive element.

**Who receives it and why.**

- **agent orchestrator**, as Encounter: See each project's functional map, its layers, provenance, prompts and corrections in a browser, and change only what the orchestrator chooses to change there.

#### The settings schema stores the layer choice the web GUI applies.

web GUI receives from metaform command line.

**Why.** Apply the layer choice made in the browser to the project folder, so agents working there receive it, only when the orchestrator asks.

**How (Function).** POST /api/apply-layers checks and stores the --layers setting for the project's own folder through the settings schema and returns its notices.

**Relation.** The settings schema stores the layer choice the web GUI applies.

**What is there.** Viewing never changes settings; the Apply to folder button is the one control that does.

Sources: `src/metaform/modules/web/server.py`

#### The graph store answers every read the web GUI shows.

web GUI receives from data access object and metaform store.

**Why.** Show every project's map exactly as agents would see it with the chosen layers, and change stored data only by peeling the top correction layer.

**How (Function).** The web server opens each project's store with the page's layers, or the project folder's --layers, answers each read through the same named reads as metaform query, and removes the top correction layer by peel and discard in one atomic write only while it is still the top.

**Relation.** The graph store answers every read the web GUI shows.

**What is there.** Reads include roots, pages of the whole map in address order with each element's nearest parent, provenance, stack and peel-preview, which shows what removing a correction layer would change before the warning.

Sources: `src/metaform/modules/web/server.py`

### Metaform specification

`document.specification`, read as "specification document", is a notable element.

**Who receives it and why.**

- **agent orchestrator**, as Encounter: Hand every agent building Metaform one current contract to build from, with the reason for each requirement and the tests that protect it, so the build serves the design and not an agent's guess.

#### The test suite protects the specification's requirements in the build.

Metaform specification receives from tests and CI.

**Why.** Have each requirement's acceptance protected by a test that fails on a wrong build, on Linux, macOS and Windows, on every change.

**How (Function).** The test suite marks each test with the requirement it protects and whether it is a fixture, simulation or real run, runs the real CLI in an isolated home, drives the web GUI in Chromium through Playwright, and runs with strict pyright and Ruff on six CI jobs.

**Relation.** The test suite protects the specification's requirements in the build.

**What is there.** All 482 tests pass locally in about four minutes and pyright in strict mode reports no errors; Ruff reports 117 findings.

Sources: `tests`, `conftest.py`, `src/metaform/modules/intake/tests`, `src/metaform/modules/map/tests`, `src/metaform/modules/memory/tests`, `src/metaform/modules/mcp/tests`, `src/metaform/modules/web/tests`, `src/metaform/modules/helloworld/tests`, `src/metaform/modules/template/tests`

- **CI**, `code.integration.continuous`, read as "continuous integration code" (Function). The checks workflow installs with uv, installs Chromium for the web GUI checks, then runs pyright, Ruff and pytest on Ubuntu, macOS and Windows with Python 3.11 and 3.14 for every push and pull request, each check reporting on its own and a newer push cancelling the older run. Continuous integration proves the build on all three systems. What is there: .github/workflows/checks.yml; the template module carries its own copy for module repositories. Sources: `.github/workflows/checks.yml`, `src/metaform/modules/template/.github/workflows/checks.yml`. Finding: broken. The lint step fails on every job: Ruff 0.16.9, pinned, reports 117 findings over src, tests and conftest.py under its default rules, most of them import order, subprocess.run without check and datetime.UTC; Q47 is open.

### data access object and metaform store

`code.store.graph`, read as "graph store code", is a supportive element.

**Who receives it and why.**

- **map module**, as Function: Answer every map verb with exactly one data access object operation, so an agent reads what the store's rules let it see and writes only through them.
- **chassis**, as Function: Keep every registered project's metaforms in the Metaform home, never in a project folder, and let modules reach them only through one door that applies the same visibility rules on every read.
- **web GUI**, as Function: Show every project's map exactly as agents would see it with the chosen layers, and change stored data only by peeling the top correction layer.
- **intake module**, as Function: Store the whole submission as one intake layer that nothing edits afterward, and never lose an earlier intake.
- **memory module**, as Function: Keep each observation and relation at the map's own node in one memory layer that follows the same visibility rules as every layer.

### metaform command line

`code.interface.command_line`, read as "command line interface code", is a supportive element.

**Who receives it and why.**

- **chassis**, as Encounter: Run every chassis command and module verb the same way, with every switch a setting declared once, help drawn from the live declarations, and every error ending in the one command to run next.
- **web GUI**, as Function: Apply the layer choice made in the browser to the project folder, so agents working there receive it, only when the orchestrator asks.
- **MCP module**, as Function: Check each tool call's arguments exactly as the command line would, and fail with the command line's next step.

#### The plugin system gives the command line the module verbs it runs.

metaform command line receives from module contract and loader.

**Why.** Parse and run each module verb from its one declaration, with the settings it reads as its switches and its help page drawn from that declaration.

**How (Function).** The plugin system hands the command line each enabled module's verbs with their nouns, switches, caution, supported systems and surfaces, and the default verb.

**Relation.** The plugin system gives the command line the module verbs it runs.

**What is there.** A verb declared for MCP only is not a command; a verb outside this system says where it runs; metaform <module> alone runs the module's default verb, so metaform web runs start.

Sources: `src/metaform/cli.py`

### tests and CI

`code.suite.test`, read as "test suite code", is a supportive element.

**Who receives it and why.**

- **Metaform specification**, as Function: Have each requirement's acceptance protected by a test that fails on a wrong build, on Linux, macOS and Windows, on every change.

## 5. Findings

- **code.integration.continuous**: broken. The lint step fails on every job: Ruff 0.16.9, pinned, reports 117 findings over src, tests and conftest.py under its default rules, most of them import order, subprocess.run without check and datetime.UTC; Q47 is open.
- **code.verifier.skill**: missing. MCP-022 has no verification per tool.
- **code.launcher.variant**: missing. PROJ-019 is confirmed and not built.
- **code.export.origin**: missing. PROJ-020 and PROJ-021 are not built, waiting on section 08 questions 5 and 13.
- **code.tool.knowledge**: missing. map knowledge takes no ef noun, so joins and subtypes a knowledge layer adds, and corrections made through the tool, cannot carry the Function or Encounter word MAP-020 gives every join; an ef= given goes to extra.
