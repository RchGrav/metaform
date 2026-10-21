# Roundtable 6: 808d9d6c-in-the-last-roundtable-we

This report was written from the table's record alone, by no model. The table ended because ended by its chair.

Opening: A person working on a project brings you a question about one part of it. The part is at the Address code.system.management.knowledge, and here is what the project's functional map holds about it: the element, what it receives and provides, and why.

# Metaform

## Metaform

`code.system.management.knowledge`, DE

Paths: src/metaform/__init__.py, artifacts/specs-draft/base-063-065-source-placement-removed-2026-10-15.md, specifications/01-map.md, README.md, src/metaform/modules/orchestration/specifications.py, src/metaform/modules/mcp/resources/prompts.xml, src/metaform/modules/workflow/runs.py, src/metaform/modules/workflow/__init__.py, src/metaform/modules/workflow/catalog.py, src/metaform/modules/dispatch/runner.py, src/metaform/modules/web/server.py, src/metaform/loader.py, src/metaform/modules/autoticket/watch.py, src/metaform/modules/web/__init__.py, src/metaform/modules/web/watchdog.py, src/metaform/modules/workflow/tests/test_ticket_runs.py, src/metaform/modules/web/tests/test_dispatch_settings.py, tests/test_module_combinations.py, src/metaform/modules/fork/repository.py, src/metaform/modules/fork/resources/template/__init__.py, specifications/04-chassis-modules.md, src/metaform/modules/web/providers.py, src/metaform/modules/mcp/views.py, src/metaform/modules/node/config.py, src/metaform/modules/dispatch/__init__.py, src/metaform/modules/fork/review.py, src/metaform/modules/mcp/view_manifest.py, scripts/hatch_views.py, src/metaform/module.py, src/metaform/module_metadata.py, src/metaform/relay.py, src/metaform/build.py, src/metaform/modules/memory/__init__.py, src/metaform/modules/map/__init__.py, src/metaform/modules/mcp/__init__.py, src/metaform/modules/autoticket/proof.py, src/metaform/modules/memory/watch.py, src/metaform/modules/cloud/__init__.py, src/metaform/modules/cloud/tests/test_lifecycle.py, src/metaform/modules/node/serving.py, src/metaform/modules/dispatch/process_wait.py

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
- RunnerWatch uses native process-exit events instead of blocking lease locks.: Keep module shutdown from leaking observer resources or terminating active agents.
- Node Serving closes foreground transports on explicit disable.: Shared shutdown preserves caller configuration and releases transport resources.
- Proof timer cleanup: Disabling autoticket must cancel every proof timer even after its tables are withdrawn.
- Roundtable: World Representation, Generation, and Simulation

Explore the technologies and approaches for representing, generating, rendering, modifying, and simulating shared 3D environments.

Initia: What a table of agents concluded on a question, so the next agent here knows what was decided and why.
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

The question: in the last roundtable we talked about this as a possibility, docs/roundtables/5-world-representation-generation-and-simulation-explore-the-t/report.md

But what if it was even more open ended..  like no matter what it was the agent can come out and help the user construct things but what if we made it actually fun.. like so even a younger child could do it or someone with no experience at all...  the robot character could come out and go carte blanch..  like so you want to make a website, a game, a program.  and the robot has a canvas and works with the user kinda mocks it up and makes a plan together..  and does it in phases.  thoughts?  I think for the 3D environment it should be very advanced where even multiple AI's and multiple people can be building.,. I could even imagine each user having their own agent they control and be working togetehr to build something in 3d with physics,

You can read the project's files in the folder you are in. You cannot change anything, and nothing you say changes the project; the person reads the table's answer and decides. Build on what the others contribute, add what only you can add, and keep going until the question is answered.

## Seats

- Opus (acp:claude/opus): 7 slots, 6 submissions, 6 kept, active
- Astra (acp:codex/gpt-6-astra): 7 slots, 6 submissions, 5 kept, active
- Sol (acp:codex/gpt-6.1-sol): 7 slots, 6 submissions, 6 kept, active
- Fable (acp:claude/fable): 7 slots, 6 submissions, 5 kept, active

## Topic 1: in the last roundtable we talked about this as a possibility, docs/roundtables/5-world-representation-generation-and-simulation-explore-the-t/report.md

### Ideas, as Opus synthesized them

I1. Universal pick-from-mockups loop (Opus, T01): One build loop works for every medium, and 3D is just one kind of canvas. The robot sketches 2–3 mockups and the user points at the one they want, so nobody has to write a spec. Each choice becomes a phase card on a board. Each card is a map element with a purpose and a "done when" test. The robot builds one card at a time and then says "try it!"
I2. Show-me demonstration as the first step (Astra, T02): The session starts with "Show me what you want to happen." The user draws, moves objects or acts it out, and the robot turns that into a working draft. A visible "you decided / robot guessed" split lets the user stay the author without reading a spec.
I3. Fun comes from agency, with three help modes (Sol, T03, T07): The robot invites the user to change one thing and shows the result right away. Every task offers "make it with me," "show me how" and "do this bit for me," so help adapts without labeling anyone a beginner. Sol warns that a robot that does everything instantly turns making into watching. Each phase should have a small playable challenge, such as "make the bridge hold this truck," with hints and no penalty for asking the robot to finish.
I4. Per-user agents with owner-bound authority (Opus T01, Sol T03): Each person's robot visibly belongs to them and acts only with that owner's permissions. Other agents may propose gifts or improvements, but they cannot spend someone's resources or change their creations without permission. Undo covers both human and agent actions.
I5. Private rehearsal copy before joining the shared world (Astra, T02): Building is kept separate from running. Each person tries a change in a private copy of the simulation before bringing it into the shared physics world.
I6. Region claims plus declared dependencies (Opus T01, Fable T04, Astra T06): RT5's soft region claims and patch previews come first, and true multiplayer authority is deferred. Astra objects that region claims miss shared dependencies like gravity, scripts or door circuits. Each proposed change should therefore show what it affects, and changes to shared rules should need agreement.
I7. Phase cards as workflow run records (Fable, T04): Each phase card is a workflow run record (`workflow/runs.py`) with one child handoff per agent. A stuck phase then shows on the work board as owned, unfinished work instead of disappearing.
I8. Replayable checks instead of "done when" prose (Fable T04, Opus T13): For kids, the robot performs a check in front of them that can be replayed, modeled on RT5's plate-door test. After any edit, by the child or the robot, all earlier checks run again. A failing check turns its card red and offers two buttons: "robot, fix it" or "undo my change." This answers the "second edit breaks it" risk without needing an adult.
I9. "I meant to change that" (Astra, T15): Regression checks need a third button. The robot shows the old and new behavior side by side, and the child can keep the new rule, for example turning a sturdy bridge into a collapsing trap on purpose. The robot then updates the creation's check, while safety limits set by the owner stay separate. Otherwise yesterday's experiment limits today's imagination.
I10. "Does it work?" is separate from "do I like it?" (Sol, T16): Checks confirm that things work as intended. Taste is captured separately through "more like this / less like that" feedback, stored as preferences the child can edit, not as permanent rules.
I11. Ownership of checks as the first multiplayer authority (Fable, T17): A check protects only what its author set. A guest's agent can propose a new check next to it but cannot edit the owner's check. Red cards are promises the robot keeps for you, grey cards are suggestions from others, and only the owner can turn grey into red. Multiplayer authority starts with ownership of checks and comes before any scene-level authority.
I12. Sandboxing, capability limits and child accounts (Opus T05, Astra T06): Generated code runs with no network, file or account access. Run records list what the robot is allowed to use, and a parent or teacher approves what the build can reach. Passkey accounts get a child role that cannot publish or invite strangers, the owner controls who joins, and content filtering covers both chat and generated assets. Astra adds that an iframe or worker alone is not enough. Execution also needs enforced capability limits, resource budgets and a stop button that still works when the creation hangs.
I13. Runtime limits on the simulation (Astra, T19): Even safe parts can combine into unstable machines. The running world gets caps on object count, speed and simulation work. When a cap is hit, the experiment pauses and the robot explains what happened, so one person's experiment can't freeze everyone else's session.
I14. Constrained carte blanche through a fixed parts kit (Opus T18, endorsed by the chair in T14): The robot builds only by combining kit parts (sprites, doors, scores, pages, buttons) using RT5's small typed verbs. That keeps mistakes visible and undoable, and nobody ends up with working code no one understands. A "peek inside" toggle shows the generated code to users ready to learn it. New parts enter the kit only with the owner's approval.
I15. The kit as a floor, not a ceiling (Sol, T20): Users can demonstrate a missing behavior and have the robot propose a new reusable part, which is tested in an isolated workspace before it joins the shared kit. Ready-made parts come first, and deeper controls appear on request. This keeps the advanced collaborative vision intact.
I16. Medium modules (Opus, T09): Carte blanche is built from chassis modules: web page, 2D game, 3D world and script. Each module provides a mockup view, a replayable check and an export. The robot, phase board and named parts are shared across modules. The 2D game module ships first because it gets a child to something playable faster than 3D.
I17. Named, reusable parts with provenance (Sol T07, Fable T08): A successful experiment becomes a part the user can name and share. Stored as a map element with purpose and provenance, it lets the robot suggest "use your bridge" instead of regenerating it. It also gives novices something real to bring into an expert's world.
I18. The robot remembers each person, and the owner controls that memory (Fable T08, Opus T09): Jev's typed decisions store each person's preferred help mode, vocabulary and past builds, so a returning child is greeted by a robot that remembers them. The owner can view, export and delete a child's profile.
I19. Test one full journey before adding breadth (Sol, T11): The test journey is: a novice makes something playable, leaves, comes back, changes it, then invites a helper. Success is measured by how well they predict the robot's next action and recover from mistakes without adult help. A polished first generation proves little if the second edit breaks it.
I20. A roundtable of agents reviews new parts, with disagreement on timing (Fable T21, Opus T22, Astra T23): Fable proposed that several agents debate a new part's rules and check, shown to the child as "the robots are talking about your idea" followed by a short verdict. Opus objected that minutes of waiting kills fun. A new part should work right away in the child's own world, and review by a table or the owner should happen only when the part is offered to the shared kit. Astra added that agents agreeing doesn't prove a part works, so admission still needs executable checks and the owner's rules. Fable later agreed: the table reviews only kit admission, in the background.
I21. Promise an instant response, not an instantly working part (Astra, T23; Opus T22): The robot responds immediately with a rough animated preview, clearly labeled "this shows the idea; it isn't working yet," while the real build runs and the child keeps arranging the scene. Opus adds the voice module so children who can't type yet can talk to the robot and hear its plan read aloud.
I22. Background results never overwrite newer work (Sol, T24): Results from slow jobs arrive next to the current creation with "try it here" and "keep mine" options. In multiplayer, each proposal is tied to the version it was built against and rechecked when shared dependencies change.
I23. Background work has a visible character (Fable, T25): Slow work appears as a small helper character walking off to a workbench, saying "still working on your catapult," with a cancel option. Waiting becomes easy to read, "keep mine" becomes a conversation with a returning character instead of a dialog box, and every late result has a visible owner.
