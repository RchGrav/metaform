# metaform functional map

## module author

`stakeholder.author.module`, VE

### module author receives from plugin system

module author declares a module once in its own folder and receives its command, help page, tool and settings from that one declaration

Why: Add a capability to Metaform as a module of its own, declared once, that behaves like every built-in module on the command line and over MCP and keeps working as the chassis changes.

Not: It does not let one module import another; modules cooperate through events.

- example module: shows each feature of the contract working once, each with a test that fails if the chassis drops it
- extension guide: walks a module author from the running example to a packaged module of their own
- module contract: states what a module must declare before the chassis will load it
- module template: gives a new module every file and declaration it needs, empty and ready to copy

## agent host

`stakeholder.host.agent`, VE

### agent host receives from installer

installer registers Metaform's server with each chosen tool, copies the skill, and proves the registered command starts a working server

Why: Be set up once to start Metaform's server and load its skill, with every change to its configuration previewed and backed up, proven to work, and removable without losing any entry of its own.

Not: It installs no software itself, not even uv, and writes nothing into a project folder.

- probe client: starts the registered command and passes it only when it answers initialize and lists at least one tool
- agent skill: tells an agent to ask Metaform itself for the live state and the next step

### agent host receives from package builder

agent host runs python on the wheel file and gets a working Metaform with a home of its own and no network needed

Why: Run a custom Metaform inside a code execution sandbox that has no network and nothing installed, without touching any Metaform installed beside it.

Not: It never replaces, downgrades or changes an installed Metaform, its dependencies or its data.

- bootstrap: puts the wheel first on the import path and gives it a home of its own before running Metaform

### agent host receives from mcp server

agent host launches metaform mcp serve through uvx and lists the tools and instructions of the folder it started in

Why: Start Metaform in an environment of its own, the same way on every system, and give the agents it runs every Metaform capability as tools, with the instructions for using them.

Not: It serves one host over stdio on this machine; remote hosting comes later, and no tool takes a nonce.

## agent orchestrator

`stakeholder.orchestrator.agent`, VE

### agent orchestrator receives from intake

intake serves the Canonical Intake by name and records the map one object per call into a building layer that no read sees until the finish

Why: Have a workpiece mapped by a subagent that reads the method from Metaform by name, word for word, so the map depends on the procedure and never on how the orchestrator reworded it.

Not: It never starts a model, never parses an intake answer as XML, and never grades what it records.

### agent orchestrator receives from correction stack

correction stack applies each finished correction on top of the intake map in order and lets only the top one be peeled off

Why: Fix what the map got wrong, move a join to the receiver it really serves, remove or add a part, explicitly and in order, so every agent stands on the same corrected map and every earlier version stays readable.

Not: It never rewrites a dependent layer; dependents are marked for re-examination and left as they were.

### agent orchestrator receives from workflow engine

workflow engine runs an authored workflow step by step, handing each step to an agent with the context it needs

Why: Run an authored workflow in any host that can run an agent, deciding when handing a step to another agent helps and whether that agent is blind to the repository, with every step carrying the context it needs.

Not: It never lives in the chassis, and the event bus never becomes its engine.

- prompt preprocessor: rewrites a prompt in the project's own names and ends each instruction with the addresses it concerns

### agent orchestrator receives from knowledge layer

knowledge layer keeps each body of knowledge as a layer answering one question, attached where it applies and toggled on for the jobs that need it

Why: Give each job exactly the knowledge meant for it at each part of the map, practices, porting notes, specifications or anything a prompt asks for, without copying knowledge into the map or building a separate map per job.

Not: It never changes the intake map or a correction; only a correction layer changes the metaform.

- transitive property: applies from its element toward the leaves and shows toward the trunk
- layer selection: resolves the layers that reach each address from the trunk toward the leaves and applies that one answer on every read

### agent orchestrator receives from agent memory

agent orchestrator adds an observation at the node it concerns, and the next agent that opens that node reads it there

Why: Have a small wrong inference, or anything a later session must remember about a part, corrected or kept at the node where the next agent reads, so the map need not be perfect to be useful.

Not: It keeps no history and no provenance; memory is meant to be cheap to add and to fix.

### agent orchestrator receives from instruction composer

instruction composer composes the agent instructions live from each surfaced module's purpose and status notice

Why: Learn on first contact with a project what Metaform is, what each module on its surface is for, and the one next step, such as having a subagent perform the intake by name, without reading any module's help first.

Not: It never copies a module's instructions anywhere that could go stale, and the skill carries none of them.

### agent orchestrator receives from question channel

agent orchestrator adds a question at the node it concerns and carries on while the person answers it in the web GUI

Why: Ask the person for clarification at the part of the map a question concerns and carry on with what does not depend on the answer, so no work stops to wait.

Not: It never blocks the asking agent.

### agent orchestrator receives from specification

specification holds each requirement with its reason, its build and the tests that protect it, as one contract a builder builds from alone

Why: Hand every builder agent one contract to build Metaform from, each requirement with its reason, its build detail and the tests that protect it, so no builder has to guess, choose or reinterpret.

Not: It records Rich's design and decides none of it; an open question blocks only the records that depend on it.

- collaboration guide: tells every agent developing Metaform how to work on it, and keeps the expert foundation out of intake
- decision record: records each design decision with the record that carries it, later decisions outranking earlier ones
- build record: records each build step and each review with what it found and what was done about it
- quality standard: sets the bar each change is judged against, item by item, before it merges

### agent orchestrator receives from blind spot analysis

blind spot analysis keeps each critic's challenges in a layer of its own and records every answer, A, B or C, beside it

Why: Find what the design lacks, functions and encounters the system should have and does not, from critics who own nothing they judge, and have each finding answered by the project so no later agent raises it again as if it had been missed.

Not: The critic answers none of its own challenges, and the answering agent approves none of its own answers.

### agent orchestrator receives from namespace tree

namespace tree names each part by an address that reads reversed as a proper noun, every prefix of it a type of its own

Why: Have each agent grasp what a part is at the level of type understanding, from an address it reads as a proper noun, before it reads any implementation.

Not: It holds no medium, encoding, genre or style in the functional map's addresses; knowledge layers may use any address.

### agent orchestrator receives from work queue

work queue keeps each part's condition as a work record beside the map, open until its task is done

Why: Line up what needs doing on the parts of the map it concerns, what is specified and not built, what is broken, what is left over, so the work can be handed out and worked through until nothing is open.

Not: It does not hold the map's shape; the intended shape stays in the map and only the difference is recorded here.

### agent orchestrator receives from settings system

agent orchestrator sets a worker's folder to its project, its commands and its layers before the worker starts, and unsets them to go back

Why: Give each worker it starts a context of its own, the project, the commands it may run and the layers it sees, without hiding the orchestrator's own commands, and put it back in one step.

Not: It is not a permission system and holds no nonce; what an agent may do is the tools it is given.

### agent orchestrator receives from chassis

chassis keeps the project's Inference Metaform in the home and serves it to every agent through its command line and the modules it loads

Why: Start every agent it hands work to from the project's recorded functional map, what each part is for, who receives it, why and how, instead of having each agent rebuild that understanding from the files.

Not: It does not run agents, workflows or models; hosts start agents and the orchestrator hands them work by name.

### agent orchestrator receives from variant store

variant store stores each worker's result as the files that differ from one origin and rebuilds any of them with Python alone

Why: Keep what every worker produced in its worktree or workfolder, committed or not, against one baseline, and bring any of those results back out anywhere, even without git or the repository.

Not: It never makes one variant the baseline of another; only a new origin moves the baseline.

### agent orchestrator receives from map api

map api returns, for one address, what relies on it, what it relies on and what the layers in context hold there

Why: Hand a worker one address and have it read, before it changes anything, what relies on that part, what that part relies on, and what the layers in context hold there, instead of reading the implementation to find its place.

Not: It computes no visibility of its own; select, mask and hiding are applied inside the store's reads.

## project owner

`stakeholder.owner.project`, VE

### project owner receives from feedback channel

project owner reads each report, feedback and shape file an agent left, listed by kind and by layer

Why: Hear from the agents working on its project, in their own words, what they found wrong with the project and with Metaform, and read any result an agent could not submit.

Not: Nothing submitted is refused, and the settings decide only what agents are asked for, never what is kept.

### project owner receives from project registry

project owner registers a workpiece by its folder and target, and clears its metaforms whenever it wants the intake taken again

Why: Bring a workpiece under Metaform by its folder and what it is, and take its map again from nothing whenever the intake should be redone, while the workpiece's files, settings and history stay as they are.

Not: Clearing never touches the project's folder, its settings or its history of origins and variants.

- project reset: removes a project's metaforms and reports after saying what goes and what stays, and names whatever it could not remove

### project owner receives from blind spot analysis

project owner approves a challenge answered B on the command line, and it becomes a plan with the element and join it proposed

Why: Decide which of the project agent's beneficial answers become new work, since agreeing to new work is the owner's decision.

### project owner receives from map viewer

project owner watches the map grow as the intake records it and selects any node to read its full record

Why: Watch the map of any registered project take shape as the intake records it, check every object's words, purposes, functions, observations, conditions and provenance in one place that shows exactly what agents would receive, and improve the prompts that made its layers.

Not: Viewing never changes a setting or the map; memories, answers, knowledge and corrections are written through the tools, not the page.

- prompt editor: saves an edited prompt as its next version and never changes the version a layer was made from
- web server: serves every project's GUI from one server per home and pushes each change to every open page

### project owner receives from user guide

user guide leads a reader from what Metaform is to a first map and on to reading, keeping and extending it

Why: Understand what Metaform does for its workpiece and run it, from installing and connecting an agent to reading the first map, with every command runnable as written and every claim checkable against the source.

Not: It never presents intended functionality as shipped; lexicalization and automated blind-spot production are described as mechanisms, not commands.

- technical reference: ties each mechanism to its source, its tests and the evidence still to collect
- agent definition: instructs an agent to keep the README and docs readable and true to the source without touching the code
- research paper: develops the complete causal account of the method for readers who need the mechanism, with how to cite it

## context engine

`code.engine.context`, AUE

Paths: src/metaform, specifications, docs, tests, README.md, pyproject.toml, .github/workflows/checks.yml

### context engine receives from chassis

chassis holds the functional map with its layers and carries every other capability as a module loaded onto it

Why: Prepare a workpiece's functional understanding once, before the work, and hand it to every later agent, session and operation, so the inference an agent would spend orienting itself is spent in advance and amortized.

## chassis

`code.chassis`, DE

Paths: src/metaform/cli.py, src/metaform/home.py, src/metaform/data, src/metaform/loader.py, specifications/spec/04-chassis-modules.md

### chassis receives from command line interface

command line interface reads every command as a verb with its nouns and switches and ends every error with the one next step

Why: Run completely on its own from one command, so a person or an agent without MCP reaches every capability, every call reads the same way, and every failure names the one command to run next.

Not: It never waits on a prompt without a terminal; anything a prompt would ask can be given on the command line.

- help system: builds every help page from the live declarations, so no module writes help anywhere else
- command parser: parses a call by the same rules whether it arrives as words on the command line or as JSON over MCP
- query: answers each of the design's questions with one store read, with no module needed

### chassis receives from graph store

graph store stores each metaform as one row per thing in its own SQLite file and answers every read through an index, applying select, mask and hiding inside the read

Why: Own every piece of Metaform data in one place that the command line, MCP and every module reach the same way, so nothing a module keeps is lost, leaks between projects or slips past what an agent is allowed to see, and a project can be carried whole to another home.

Not: It offers no general SQL surface and never judges whether an address is functionally valid.

- project exchange: writes a project to one JSON document by unique id and adds back only what the target does not hold

### chassis receives from project registry

project registry resolves each folder to its project, and each project to its active metaform, from the home alone

Why: Know every registered project, the folder each agent works from, and which of a project's metaforms is active, without writing anything into any project folder.

Not: It keeps no marker, cache or database in a project folder.

### chassis receives from event bus

event bus delivers each published topic to every subscribed module with a Context of its own and returns every delivery's outcome

Why: Let modules act on what happened elsewhere, a greeting recorded, a map changed, without importing each other and without any module having to announce its own writes.

Not: It runs no workflow: no retry, no delay, no ordering beyond declaration order and no persistent queue, BASE-033.

- change announcer: fires map.changed once for each metaform a finished command changed

### chassis receives from settings system

settings system resolves each setting from this call's switch, then the nearest folder's stored value, then its declared default

Why: Let every behavior a person or an agent can ask for once also be a standing choice, declared once, that works with no configuration and survives a module being turned off.

Not: It never writes a default into storage, so a later release's default reaches every folder still at default.

- settings screen: stages every change to settings and modules until it is previewed and saved

### chassis receives from plugin system

plugin system loads each module as one owned unit and withdraws everything it registered when it goes, while its data stays

Why: Carry every capability beyond its own commands as a separately owned module, so a module can be added, turned off or removed without the chassis naming it and without losing the data it kept.

Not: It gives a module no private way to the data or the command line; whatever two modules need goes into the common base.

- module loader: reads each module's declarations from its source before any of its code runs and imports only the enabled, compatible ones

## blind spot analysis

`code.analysis.blind_spot`, SE

Paths: src/metaform/data/challenges.py

## map api

`code.api.map`, SE

Paths: src/metaform/modules/map

## package builder

`code.builder.package`, SE

Paths: src/metaform/build.py, src/metaform/_build_info.py

## event bus

`code.bus.event`, SE

Paths: src/metaform/events.py, src/metaform/changes.py

## feedback channel

`code.channel.feedback`, SE

Paths: src/metaform/reports.py

## question channel

`code.channel.question`, SE

## instruction composer

`code.composer.instruction`, SE

Paths: src/metaform/instructions.py

## workflow engine

`code.engine.workflow`, SE

## installer

`code.installer`, SE

Paths: src/metaform/install.py, src/metaform/probe.py, src/metaform/skill/SKILL.md

### installer receives from package builder

package builder writes one wheel of the chassis and the enabled modules and records its path as the last build

Why: Register a server that starts from a known wheel holding exactly the modules the user has enabled.

## intake

`code.intake`, SE

Paths: src/metaform/modules/intake

### intake receives from intake procedure

intake procedure defines the method that turns a workpiece into its map, from its vested entities through each receiver's purpose to the functions that serve it

Why: Hand every intake agent one fixed method for turning a workpiece into its functional map, the same text each time, so every map comes from the same procedure.

Not: It does not grade the map it produces; intake is never gated or judged.

### intake receives from feedback channel

feedback channel writes the intake's report and feedback to files named by its layer and ties them to that layer's provenance

Why: Keep the intake agent's report on the project and its feedback on the process with the intake layer's provenance, so each finding stays tied to the run that produced it.

### intake receives from graph store

graph store keeps the intake layer building and out of every read in context until the intake finishes

Why: Keep a half-recorded map away from every agent until the intake finishes, and let the next agent resume an intake that an interrupted one left.

## command line interface

`code.interface.command_line`, SE

Paths: src/metaform/cli.py, src/metaform/grammar.py, src/metaform/docs.py, src/metaform/results.py, src/metaform/query.py

## knowledge layer

`code.layer.knowledge`, SE

Paths: src/metaform/data/layering.py, src/metaform/data/selection.py

### knowledge layer receives from prompt store

prompt store keeps every prompt as numbered versions that never change and records the version each layer was made from

Why: Tie each layer to the exact prompt text it was made from, so a prompt can be improved for later runs while every existing layer still shows the text that produced it.

Not: It never edits a version in place; an edit is always the next version with its parent.

## agent memory

`code.memory.agent`, SE

Paths: src/metaform/modules/memory

## work queue

`code.queue.work`, SE

Paths: src/metaform/data/writes.py, src/metaform/modules/map/__init__.py

## project registry

`code.registry.project`, SE

Paths: src/metaform/home.py, src/metaform/context.py

## mcp server

`code.server.mcp`, SE

Paths: src/metaform/modules/mcp

### mcp server receives from plugin system

plugin system supplies each surfaced module's verb declarations, from which every tool's name and input schema are built

Why: Serve every module's verbs as tools with no MCP code written in any module, and never list or run a tool the folder's command surface hides.

## correction stack

`code.stack.correction`, SE

Paths: src/metaform/data/corrections.py

## graph store

`code.store.graph`, SE

Paths: src/metaform/data, src/metaform/sqlite.py

## prompt store

`code.store.prompt`, SE

Paths: src/metaform/data/prompts.py

## variant store

`code.store.variant`, SE

Paths: src/metaform/data/history.py

## test suite

`code.suite.test`, SE

Paths: tests, conftest.py

## plugin system

`code.system.plugin`, SE

Paths: src/metaform/module.py, src/metaform/loader.py, src/metaform/module_metadata.py, src/metaform/modules

## settings system

`code.system.settings`, SE

Paths: src/metaform/settings.py, src/metaform/tui.py

## map viewer

`code.viewer.map`, SE

Paths: src/metaform/modules/web

### map viewer receives from event bus

event bus delivers each map.changed to the web module, which hands it to the running server for every open page

Why: Redraw every open page the moment a project's map changes, from the command line, over MCP or from another page, and send no request while nothing happens.

Not: The page never polls and the server never pushes around the bus.

### map viewer receives from graph store

graph store answers each of the page's reads with the store read agents get, visibility applied inside it

Why: Show a person exactly what agents are shown, no more and no less, so checking the map in the browser checks what agents receive.

## namespace tree

`data.tree.namespace`, SE

Paths: src/metaform/data/names.py, src/metaform/data/roots.json

## user guide

`document.guide.user`, SE

Paths: README.md, docs

## intake procedure

`document.procedure.intake`, NE

Paths: specifications/Canonical_Intake.xml, src/metaform/modules/intake/resources/Canonical_Intake.xml

## specification

`document.specification`, NE

Paths: specifications/spec, specifications/README.md

### specification receives from intake procedure

intake procedure gives the map's shape in its response schema, which the spec maps field by field onto the tools and the store

Why: Take the map's shape, its concepts, roles, joins and subtype joins, from the one schema the intake follows, so the store and the tools hold exactly what an intake produces.

### specification receives from test suite

test suite fails whenever a build gets a requirement wrong, each test naming the requirement it protects

Why: Have every requirement protected by a test that fails on a build that gets it wrong, and by nothing written for show, so a wrong build cannot pass as the design.

Not: A passing run is never taken as proof of quality; the code itself is judged against the standard by a critic.

- traceability check: stops the test run when a test names no record of the spec or no kind of run
- continuous integration: runs type checks, lint and every test on three systems and two Pythons for each push
