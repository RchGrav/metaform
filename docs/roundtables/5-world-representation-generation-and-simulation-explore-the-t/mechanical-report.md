# Roundtable 5: 5ebe493b-world-representation-generation-and-simulation

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
- MCP provides its resolved connection rules through agent.rules.: Preserve prompt edits and delivery identity when optional modules disappear.
- Roundtable: World Representation, Generation, and Simulation

Explore the technologies and approaches for representing, generating, rendering, modifying, and simulating shared 3D environments.

Initia: What a table of agents concluded on a question, so the next agent here knows what was decided and why.
- Web provides theme text through web.theme.tokens.: Keep optional web integrations behind public provider boundaries.
- Module state mutations relay module.changed only after the complete batch commits.: Keep transition notifications consistent with committed state and owned resource lifetimes.
- Dispatch requires the ticket.runtime capability for map-owned work operations.: Explain why removing map requires disabling dispatch.
- Module.uses names consumed Provides kinds.: Preserve runtime and build dependency checks without importing disabled modules.
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

The question: World Representation, Generation, and Simulation

Explore the technologies and approaches for representing, generating, rendering, modifying, and simulating shared 3D environments.

Initial ideas include data structures, sparse octrees and sparse voxel octrees, SDFs, Marching Cubes, Dual Contouring, hybrid representations, procedural chunks and regions, dynamic geometry, concave deformation, destruction, materials, physics, environmental systems, persistence, and large-scale simulation.

Alternatives, unconventional combinations, and entirely different approaches are within the topic.

**Question:** What is the perfect signature environment for ai and user collaboration in metaform to create 3D interactive experiences?

You can read the project's files in the folder you are in. You cannot change anything, and nothing you say changes the project; the person reads the table's answer and decides. Build on what the others contribute, add what only you can add, and keep going until the question is answered.

## Seats

- Sol (acp:codex/gpt-6.1-sol): 8 slots, 8 submissions, 8 kept, active
- Astra (acp:codex/gpt-6-astra): 8 slots, 8 submissions, 8 kept, active
- Fable (acp:claude/fable): 8 slots, 8 submissions, 8 kept, active
- Opus (acp:claude/opus): 8 slots, 8 submissions, 7 kept, active

## Topic 1: World Representation, Generation, and Simulation

### Ideas, as Sol synthesized them

I1. Shared canvas with retained intent: Humans and AI create playable 3D experiences together, moving between editing and play. Meaningful objects and rules link to purpose, constraints, provenance and decisions through Metaform.
I2. JavaScript-first implementation: The eventual preference was TypeScript, Three.js, Rapier WASM and Web Workers. Earlier alternatives included Godot web exports with headless workers, or Bevy compiled for both browser and server. Add engine complexity when concrete requirements justify it.
I3. Minimal playable editor: Begin with a blank canvas, orbit camera, grid, selection, primitives, transforms, materials, spawn placement, undo and Play/Edit controls. The first acceptance example is a pressure plate that opens a door.
I4. Shared runtime and portable worlds: Store entities, transforms, assets and declarative behaviors in versioned JSON independent of renderer objects. Share the runtime across editor, standalone web exports and headless Node checks, with rendering optional.
I5. Authoritative scene service: A service validates commands, checks expected revisions, persists accepted edits and broadcasts changes. Human toolbar actions and agent commands use the same operation format.
I6. Stable identity and optional map links: One proposal made object IDs directly equal Metaform addresses. An alternative separates stable UUIDs from optional functional-map links, allowing ordinary scene objects without requiring a purpose entry for each one.
I7. Agent controls: The proposed control vocabulary converged on observe, probe, sketch, propose, preview, commit, check, claim, step and reset. Commands return revisions and typed results, use bounded batches and follow Metaform’s existing tool and resource conventions.
I8. Spatial agent perception: Combine named-camera images with semantic maps, raycasts, path queries, volume queries and addressed objects. User selections supply hit points, normals and bounds. Previews return matching before/after views, changed IDs and check results.
I9. Reviewable collaborative edits: Agents propose patches against an expected revision, preview consequences, then commit or discard. Soft region claims communicate editing intent without blocking users. Coalesce gizmo drags into readable operations and retain authorship and reasons.
I10. Declarative behavior rules: Represent interactions as inspectable event-condition-action rules, such as plate entry plus possession of a key opening a door. Begin with a fixed behavior library. Sandboxed scripting was suggested as a later fallback.
I11. Isolated play and explicit multiplayer authority: Start each Play session from an authored snapshot so runtime changes cannot alter the canvas. Explicitly retain selected runtime changes. Shared editing comes first, while multiplayer later requires one authoritative simulation host.
I12. Persistence through snapshots and operations: An early proposal treated intent operations as authoritative and geometry as rebuildable caches. The counterproposal requires authoritative snapshots plus edit history because intent alone cannot replay reliably after terrain or generator changes. Record versions, inputs and resolved results.
I13. Branching and merging by purpose: Pause, branch and compare scenarios, then merge selected edits with purpose-aware checks. Metaform workflow runs, tickets and typed judgments were proposed as the records for proposals, branches and conflict decisions.
I14. Testable intent with overridable checks: Translate purposes into bounded simulation assertions, such as a traveler crossing a bridge. Distinguish hard constraints from advisory findings, since flooding may be intentional gameplay. Retain accepted exceptions and reasons so agents respect them later.
I15. Explicit simulation assumptions: Report the character, rainfall, fidelity and other conditions behind a result. Early fixed-point physics everywhere was challenged as unnecessarily restrictive. The later direction favors fixed ticks, seeded randomness, checkpoints and repeatable bounded tests.
I16. Rapier physics foundation: Consensus favored rigid bodies, colliders, joints, sensors and raycasts. Expose static, dynamic and kinematic modes, mass, friction, restitution and collision groups. Use primitive or compound convex colliders for movable concave objects.
I17. Repeatable physics checks: Run the same Rapier build in browser and Node, use a fixed timestep and stable body insertion order, and support step counts and sensor assertions. The final proposal selected the enhanced-determinism package and snapshot restoration for resets and preview checkpoints.
I18. Visual particles and simulation budgets: Begin with particles triggered by collisions and broken joints that do not affect physics. Cap active bodies, fragments and particles to keep generated scenes responsive.
I19. Staged destruction: First break authored joints into a bounded number of rigid pieces. Alternatives included pre-fractured Voronoi props, impact-time voxelization and detached terrain components. Arbitrary fracturing and terrain collapse were deferred, with rubble eventually settled into cached debris.
I20. Hybrid world representation: Use entity-based actors, mesh buildings and props, and editable SDF terrain where sculpting is needed. Keep semantic features and references independent of individual voxels and rendering caches.
I21. Sparse terrain storage and octrees: Store SDF terrain in sparse bricks indexed by a chunk hash, with 32³ bricks proposed. Consensus deferred octrees and SVOs until measured spatial-query or distant-LOD needs justify them. An octree is an indexing choice rather than the world model.
I22. Terrain meshing alternatives: Marching Cubes offers a simpler initial implementation with seam tests. Dual Contouring better preserves sharp features but adds fitting and topology complexity. Remesh dirty chunks in workers and publish matching meshes and colliders against the same revision.
I23. Shape, materials and structural behavior: Separate SDF shape from material properties such as density, strength and permeability, and distinguish cosmetic paint from physical changes. SDF operations support concave carving, but collapse requires a structural model beyond subtraction.
I24. Procedural generation and chunk persistence: Use editable, parameterized generators such as villages defined by seed, footprint and style. Persist generator versions, changed bricks, snapshots and edit deltas while regenerating untouched chunks. Generator upgrades must preserve authored edits.
I25. Stable semantic terrain features: Extract caves, ridges, shorelines and overhangs into addressed features for agent queries. Match changed regions to prior identities by overlap and record splits as explicit refinements so purpose references survive sculpting.
I26. Environmental simulation at multiple scales: Maintain coarse water, heat and ecology state in distant chunks, activating detailed simulation nearby. Exchange conserved quantities across boundaries. A stream might use drainage estimates during editing and local fluid simulation during play.
I27. Incremental delivery and concrete benchmarks: Establish primitives, plate-to-door behavior, persistence and the agent edit loop first, then terrain and broader automated checks. A hillside settlement with a tunnel, redirected stream and bridge provides a later integration benchmark. Multiplayer waits for demonstrated demand.

### Rankings, best first

Sol: I3, I27, I5, I4, I2, I7, I16, I9, I11, I8, I10, I12, I6, I1, I18, I14, I15, I19, I17, I20, I21, I22, I23, I24, I13, I25, I26

Astra: I1, I27, I4, I5, I7, I8, I3, I2, I16, I11, I10, I12, I6, I9, I18, I14, I15, I17, I19, I20, I21, I23, I24, I22, I13, I25, I26

Fable: I1, I5, I3, I7, I4, I2, I12, I9, I10, I14, I16, I17, I11, I27, I8, I13, I6, I15, I20, I25, I24, I21, I22, I18, I19, I23, I26

Opus: I1, I4, I5, I7, I3, I27, I9, I14, I8, I10, I11, I2, I17, I16, I12, I6, I15, I13, I20, I25, I18, I19, I21, I24, I22, I23, I26

### Borda count (derived)

Derived: a Borda count over the rankings that were read (of n ideas, first earns n - 1 points, last none). The raw rankings are the record; nothing in the protocol depends on this.

I5. Authoritative scene service: 96 points
I4. Shared runtime and portable worlds: 94 points
I3. Minimal playable editor: 92 points
I1. Shared canvas with retained intent: 91 points
I7. Agent controls: 89 points
I27. Incremental delivery and concrete benchmarks: 84 points
I2. JavaScript-first implementation: 77 points
I9. Reviewable collaborative edits: 71 points
I8. Spatial agent perception: 68 points
I10. Declarative behavior rules: 67 points
I16. Rapier physics foundation: 67 points
I11. Isolated play and explicit multiplayer authority: 65 points
I12. Persistence through snapshots and operations: 62 points
I14. Testable intent with overridable checks: 58 points
I6. Stable identity and optional map links: 49 points
I17. Repeatable physics checks: 46 points
I15. Explicit simulation assumptions: 39 points
I18. Visual particles and simulation budgets: 33 points
I20. Hybrid world representation: 30 points
I13. Branching and merging by purpose: 24 points
I19. Staged destruction: 24 points
I21. Sparse terrain storage and octrees: 21 points
I24. Procedural generation and chunk persistence: 16 points
I25. Stable semantic terrain features: 16 points
I22. Terrain meshing alternatives: 14 points
I23. Shape, materials and structural behavior: 11 points
I26. Environmental simulation at multiple scales: 0 points

### Top three, as each seat explained them

Sol: 1. **I3: Minimal playable editor.** It turns the blank-canvas goal into something people can use immediately. The pressure-plate-and-door example exercises object creation, spatial editing, physics sensors, behavior and play. That makes it a useful acceptance test for the whole authoring loop. Advanced terrain and destruction add less value until this loop works.

2. **I27: Incremental delivery and concrete benchmarks.** The proposed scope could become an engine project before proving useful collaboration. Staged delivery makes each addition answer a demonstrated need. First prove that a user and agent can build, save and revise an interaction. Later, the hillside benchmark can reveal whether terrain, water and structural simulation work together. This preserves room to change technical choices as evidence arrives.

3. **I5: Authoritative scene service.** Shared editing needs a clear answer to which changes were accepted and what state everyone should see. One command path for humans and agents provides revision checks, validation, persistence and broadcasts. It also gives previews and undo a reliable foundation. Its authority concerns authored scene state. Multiplayer physics authority can remain a separate, later decision.

These rank above particular geometry structures or engines because they establish the usable product, the evidence for expanding it, and the consistency needed for collaboration.

Astra: 1. I1 defines why this belongs in Metaform. A 3D editor alone offers little distinction. Linking meaningful objects and rules to intent lets an agent understand why a door must stay locked, which constraints matter, and why a user accepted a particular consequence. That retained understanding makes collaboration useful across sessions. Map links should remain optional so recording intent does not obstruct creation.

2. I27 turns a broad technology discussion into a buildable product. The plate-to-door example tests creation, selection, behavior, physics, persistence and agent editing in one small experience. It exposes integration failures before terrain, destruction and environmental simulation multiply the complexity. Later benchmarks should justify each expansion through observable user capability.

3. I4 makes the result portable and verification credible. Versioned world data and a shared runtime let the same authored experience run inside Metaform, as an exported web app, and in bounded headless checks. Separating rendering from behavior also lets agents test interactions without opening a browser. Sharing code reduces divergence, though matching engine versions, assets and settings still requires explicit checks.

These rank above individual engine and geometry choices because they establish the product’s purpose, a practical delivery sequence, and a reusable execution contract.

Fable: **I1 — Shared canvas with retained intent.** This is the answer to the question as asked. Every other idea is a mechanism; this one names what makes the environment Metaform's rather than a generic editor with an AI plugin: objects and rules carry purpose, provenance and decisions at addresses, and people move fluidly between playing the world and changing the model behind it. Without it the stack is just Three.js plus Rapier. With it, a later agent starts from retained understanding (why the tunnel floods, who the bridge is for), which is exactly the knowledge role Metaform already serves for code.

**I5 — Authoritative scene service.** This is the one architectural decision everything else depends on. One operation format for toolbar gizmos and agent commands, expected-revision checks, persistence and broadcast is what makes collaboration safe: agents can't clobber users, users can't invalidate an agent's preview silently, and every edit has an author and reason. It also keeps the engine replaceable — Godot, Bevy or Three.js are all clients of the same service — so the JavaScript-first choice (I2) carries no lock-in. Agent controls (I7), reviewable edits (I9) and snapshots-plus-ops persistence (I12) are all refinements of this single boundary.

**I3 — Minimal playable editor.** This is what lets the project exist next month instead of next year. A blank canvas with primitives, gizmos, materials, Play/Edit and the plate→door acceptance test exercises the entire collaboration loop — scene service, agent ops, declarative rules, physics, persistence — on the smallest possible world. It turns the hillside settlement, SDF terrain, octrees and destruction into measured follow-ons rather than prerequisites, which matches the chair's direction and the consensus to defer complexity until a concrete need appears.

Together: I1 says what it is, I5 says how it stays coherent, I3 says where to start. The terrain and simulation ideas rank lower not because they are wrong but because they only matter once these three are worki

Opus: **I1, shared canvas with retained intent.** This is the only idea that answers why this environment should live in Metaform and not in Three.js or Godot alone. Any editor can place a door. What Metaform adds is that the door is linked to the purpose it serves, who wanted it and why, and what was decided about it. The next agent therefore starts from that understanding instead of from bare geometry. That is the project's own stated purpose for the knowledge engineer. Testable checks (I14), Jev judgments, branching (I13) and stable feature identity (I25) only matter because of this idea. Without it, the rest is a generic web 3D editor.

**I4, shared runtime and portable worlds.** This is the decision that keeps the others honest. Saved worlds stay independent of the renderer, and one runtime serves the editor, the exported experience and the headless Node checks. So "the agent checked that the door opens" means the same thing as "the user saw the door open" and "the shipped game opens the door." If the check runtime is separate, you have two simulations that will drift apart. Agents' claims then stop being reliable, which undermines the trust the collaboration depends on. It also makes "create 3D interactive experiences" literal: the output is a standalone playable app, not just a scene inside Metaform.

**I5, authoritative scene service.** Collaboration only works if human and agent edits go through one gate with one format and revision checks. Then edits can be merged cleanly, attributed, logged and replayed. It also fits how Metaform already works: a chassis module with its own storage, change notices and lifecycle hooks. The lessons already recorded about sidecars and module.changed carry over directly. The agent controls (I7), reviewable edits (I9) and persistence (I12) are all built on this service.

**Why the rest rank lower.** The representation ideas (octrees, SDF meshing, destruction, environmental simulation) are sound but interchangeable, and they can wait. You can swap Marching Cubes for Dual Contourin

### Bottom three, as each seat explained them

Sol: - **I13: Branching and merging by purpose.** Useful later, but purpose checks cannot resolve every spatial or behavioral conflict. Reliable merging first needs stable snapshots, patch semantics and explicit conflict handling. Adding workflows and judgments before those foundations risks obscuring unresolved mechanics.

- **I25: Stable semantic terrain features.** Matching caves or shorelines by overlap is ambiguous when features split, merge or gradually move. Automatic identity could preserve the wrong reference. Start with explicitly named objects and regions, then add feature tracking when sculpting creates a demonstrated need.

- **I26: Environmental simulation at multiple scales.** This has the greatest implementation and validation burden. Switching fidelity while preserving water, heat or ecology requires careful boundary handling. It contributes little to the first playable canvas. Add a bounded environmental system when an experience actually needs it.
