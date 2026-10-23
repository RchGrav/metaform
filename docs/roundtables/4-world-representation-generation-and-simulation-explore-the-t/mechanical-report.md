# Roundtable 4: 18758bbc-world-representation-generation-and-simulation

This report was written from the table's record alone, by no model. The table ended because ended by its chair.

Opening: A person working on a project brings you a question about one part of it. The part is at the Address code.system.management.knowledge, and here is what the project's functional map holds about it: the element, what it receives and provides, and why.

# Metaform

## Metaform

`code.system.management.knowledge`, DE

Paths: src/metaform/__init__.py, artifacts/specs-draft/base-063-065-source-placement-removed-2026-10-15.md, specifications/01-map.md, README.md, src/metaform/modules/orchestration/specifications.py, src/metaform/modules/mcp/resources/prompts.xml, src/metaform/modules/workflow/runs.py, src/metaform/modules/workflow/__init__.py, src/metaform/modules/workflow/catalog.py, src/metaform/modules/dispatch/runner.py, src/metaform/modules/web/server.py, src/metaform/loader.py, src/metaform/modules/autoticket/watch.py, src/metaform/modules/web/__init__.py, src/metaform/modules/web/watchdog.py, src/metaform/modules/workflow/tests/test_ticket_runs.py, src/metaform/modules/web/tests/test_dispatch_settings.py, tests/test_module_combinations.py, src/metaform/modules/fork/repository.py, src/metaform/modules/fork/resources/template/__init__.py, specifications/04-chassis-modules.md, src/metaform/modules/web/providers.py, src/metaform/modules/mcp/views.py, src/metaform/modules/node/config.py, src/metaform/modules/dispatch/__init__.py, src/metaform/modules/fork/review.py, src/metaform/modules/mcp/view_manifest.py, scripts/hatch_views.py, src/metaform/module.py, src/metaform/module_metadata.py, src/metaform/relay.py, src/metaform/build.py

### Metaform receives from Jev

Asks typed decisions, caches answers and records actionable judgments at their addresses while preserving ordinary behavior when disabled or unavailable.

Why: Reuse typed judgments for agent allocation, knowledge ordering, triage, intake coverage and session diagnostics.

### Metaform receives from Web GUI

Serves live graph, node and layer views, source and memory inspection, work board, agent chat, attachments, diagrams, embedded apps, permissions, workspaces and build downloads.

Why: Let the person inspect the functional map and direct knowledge, work and agent activity from one persistent view.

### Metaform receives from twilio

Bridges authenticated calls and texts to the system agent and sends selected project notifications to configured owner numbers.

Why: Keep project conversation and requests for attention available away from the screen.

### Metaform receives from Roundtables

Opens controlled discussions through the external Roundtable engine, streams table events, preserves discussion records and requests a system-agent report.

Why: Examine project questions through agent discussion and preserve inspectable outcomes for later decisions.

### Metaform receives from node

Deploys the container host and manages TLS, authenticated MCP and web access, passkeys, accounts and relays.

Why: Expose project context from a host controlled by its owner.

### Metaform receives from Chassis

Discovers bundled, user, entry-point and project modules, reads declarations, loads enabled modules and withdraws their resources on unload. Shared context, settings, grammar, result formatting, reports, owned tasks and event delivery let modules supply features through the same surfaces.

Why: Extend Metaform's capabilities while retaining one consistent command, context, settings and lifecycle contract.

### Metaform receives from Inference Metaform

Stores canonical names, type addresses and CQU/DE/SE/NE roles, receiver-owned purpose joins, and versioned refinements. Reads expose entry roots, requirements, providers, namespace children, references, history, textual export and Cypher queries. Knowledge-layer operations and critic/challenge prompts support contextual analysis and recorded answers without treating semantic analysis as a storage gate.

Why: Provide a stable functional representation that relates each workpiece element to the receiving purpose its encounter serves.

### Metaform receives from voice

Transcribes microphone utterances into editable agent messages and speaks replies through selected speech engines.

Why: Converse with project agents through speech.

### Metaform receives from cloud

Signs the machine into the broker and carries authorized MCP requests over an outbound tunnel with local auditing and revocation.

Why: Let cloud AI tools reach the local map through an outbound connection.

### Metaform receives from Metaform specification

Defines map identity, layers, storage, chassis modules, CLI, MCP installation, quality, projects and viewer behavior, with acceptance conditions, status and open decisions. Trace, capture, change orders and build/review records preserve the decision trail.

Why: Preserve the settled semantics, reasons and observable requirements that determine which changes retain Metaform's intended behavior.

### Metaform receives from workflow

Registers addressed prompts. Binds variables and element values. Persists call frames, child handoffs and parallel results in project run records.

Why: Keep authored procedures callable and resumable with each call's map and folder context.

### Module developer receives from Metaform

Supplies the public chassis contract, runnable examples and template, contextual command and MCP exposure, module-owned storage, and fork checks and packaging over the released chassis.

Why: Add and maintain project-specific Metaform capabilities using a stable extension contract and distributable modules.

### Knowledge engineer receives from Metaform

Records the Inference Metaform as addressed elements and receiver-owned purpose joins, then serves the relevant map, selected knowledge, provenance and memories through agent and human interfaces.

Why: Keep a workpiece's functional identity, receiving purposes and encounter functions reusable as context so later analysis and improvement start from retained understanding.

### Automation engineer receives from Metaform

Binds callable Axiom procedures to the functional map, transports agent-interpreted calls and returns, and coordinates ticket-based agent sessions through the work board and dispatch.

Why: Run repeatable improvement procedures with the workpiece's actual context, durable handoffs and visible responsibility for unfinished work.

What has been learned and kept about this part:
- Fork packs approved module IDs explicitly: Installer defaults add onboarding modules that fork has not reviewed.
- Fork owns its scaffold template: Scaffolding must work when the template package is absent.
- The web server and watchdog listen for module.changed through the chassis relay while running.: Prevents disabled web owners from surviving or restarting after cross-process state changes.
- The web module starts its shared service only when its start hook receives Context.lifecycle equal to enable.: Prevents ordinary command cleanup from stopping the shared web service.
- Registered expertise lives at metaform://role/spatial_ui_engineer.: Future spatial UI tickets need geometry expertise distinct from state reconciliation.
- map_work op=step reads only the nouns id and said, per the op noun table in src/metaform/modules/map/__init__.py.: Agents passing text or note to map_work op=step leave empty steps in the ticket history.
- A ticket worktree's .venv lacks pytest, so uv run pytest falls through to /home/rich/metaform/.venv/bin/pytest.: A test run in a ticket worktree can pass or fail on main-checkout code and give false verification.
- src/metaform/modules/autoticket/watch.py setting() reads autoticket settings for server-held services.: Shows where autoticket's server-held services survive a module reload and what the bare fault text meant.
- loader.reset withdraws each unloaded module's settings from settings.SCHEMA.: Any long-lived service that reads module settings by key fails with a bare KeyError during a module reload.
- Module lifecycle specialist constraints: Preserve public module boundaries and deterministic resource ownership during repairs.
- Module composition and lifecycle expertise: Route module boundary and process lifecycle work to reusable expertise.
- Specialist for cross-system runtime failure review and repair.: Later tickets spanning several subsystems can reuse this role instead of creating a near duplicate.
- Control and event-processing failures reproduced and repaired: Retain tested causes and measured recovery instead of treating hidden diagnostics as proof of repair.
- Dispatch autostart endpoints use chassis.project_scope for module availability and setting access.: Prevents concurrent module refresh from breaking web settings reads.
- Web settings repair contract: Preserve existing configuration behavior during endpoint repairs.
- Web settings specialist: Reuse settings integration expertise without creating duplicate roles.
- Board operation preservation contract: Keep board grouping separate from ticket identity and completion.
- Named work board specialist: Reuse published expertise for board changes.
- Ticket inspection binds reads and saves to its opening project and base.: Preserve scope isolation during ticket inspector changes.
- src/metaform/modules/web/page/app/board/detail.js exports ticketDetail for ticket inspection.: Locate ticket inspection behavior during functional review.

The question: World Representation, Generation, and Simulation

Explore the technologies and approaches for representing, generating, rendering, modifying, and simulating shared 3D environments.

Initial ideas include data structures, sparse octrees and sparse voxel octrees, SDFs, Marching Cubes, Dual Contouring, hybrid representations, procedural chunks and regions, dynamic geometry, concave deformation, destruction, materials, physics, environmental systems, persistence, and large-scale simulation.

Alternatives, unconventional combinations, and entirely different approaches are within the topic.

**Question:** What is the perfect signature environment for ai and user collaboration in metaform to create 3D interactive experiences?

You can read the project's files in the folder you are in. You cannot change anything, and nothing you say changes the project; the person reads the table's answer and decides. Build on what the others contribute, add what only you can add, and keep going until the question is answered.

## Seats

- Argon (antigravity/argon): 1 slots, 0 submissions, 0 kept, unavailable
- Astra (acp:codex/astra): 1 slots, 0 submissions, 0 kept, left: its session ended, so it has left the table: codex offers no one model matching astra; it offers gpt-6.1-sol, gpt-6-astra, gpt-6-sol, gpt-6-luna, gpt-5.6-sol, gpt-5.6-terra, gpt-5.6-luna, gpt-daybreak-blue-latest
- Fable (acp:claude/fable): 3 slots, 3 submissions, 3 kept, active

## Topic 1: World Representation, Generation, and Simulation

### Ideas

The topic has no synthesis.
