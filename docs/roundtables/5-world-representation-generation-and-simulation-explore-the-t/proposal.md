# Proposal: a shared 3D canvas for the person and agents

Roundtable 5 (table `5ebe493b`, 2026-10-21) answered: *What is the perfect signature environment for AI and user collaboration in Metaform to create 3D interactive experiences?* The record is `mechanical-report.md` and `export.json` beside this file (27 ideas, 4 rankings, a Borda count); `report.md` is the system agent's summary. This proposal turns the answer into a goal, a plan, tickets with nodes and done-checks, an order, and the decisions left to the person. Nothing here is filed: the person approves first.

## Goal

One playable 3D world per project, edited by the person and by agents through one operation log, where every meaningful object keeps its purpose, constraints and decisions through its Metaform address. Person and agents see the same world, change it through the same operations, play it, check it, and read why it is the way it is.

Done when (the table's own acceptance, I3 and I27): a person places a pressure plate and a door; an agent wires the plate to the door from a request; in Play the door opens when a body stands on the plate; the same scene run headless gives the same result; the world survives a reload with undo intact; the door's purpose and the decision behind it are read at its address.

## What the table decided

Idea numbers are the synthesizer's (`mechanical-report.md`). Borda, best first: I5 authoritative scene service 96, I4 shared runtime and portable worlds 94, I3 minimal playable editor 92, I1 shared canvas with retained intent 91, I7 agent controls 89, I27 incremental delivery 84, I2 JavaScript-first 77, I9 reviewable edits 71, I8 spatial perception 68, I10 declarative rules 67, I16 Rapier 67, I11 isolated play 65, I12 persistence 62, I14 testable intent 58, I6 identity 49, I17 repeatable physics 46. Every seat put I3, I4, I5 and I7 in its top seven; I1 was first for Astra, Fable and Opus and 14th for Sol (`report.md` says all four put I1 in their top seven; the rankings do not). Deferred until a measured need (I27): terrain I20 to I23, generation I24, destruction I19, environment I26, branching I13, multiplayer authority I11. Left open: I6 and I12, decided below.

## What exists today

The plan builds on what is in the tree. None of it is rewritten.

- `specifications/10-world.md`, WORLD-001 to WORLD-013, confirmed 2026-10-14, cut 1: one world per project; the operation log is the authority (nine kinds, actor fields, `base_revision`, act and edit classes, undo as an appended reversal, the snapshot a cache); `functional_refs` by address; a world host behind four calls (read, subscribe, append, step); module-declared tabs; `web_see` with detail and field of view; every act answers a delta; targets by address and relation with units and frames; a seeded tick record. None of it is built: no `src/metaform/modules/world/`, no `Tab` in `src/metaform/module.py`, no `page/app/world/`. The table's I5, I4, I6, I9, I11 and I12 are these records reached again from the other side.
- The design notes behind it: `docs/research/Metaform as a Spatial Agentic Development Environment.md` (canonical scene model, the renderer never the database, Rapier first, the development loop inside the world, authoring agents and runtime characters as one embodiment system with different roles); `docs/reference/actor-identity.md` (MIN-3: an actor instance is who acted, a body is held not owned, the session is provenance); `docs/playground/actor-binding.md` (MIN-13: `actor` as a noun on the call, resolution against the observation's view frame, two seeded streams, the record's fields, overlays off the agent camera, `restore(tick)`); `docs/measurement/spatial-reference-protocol.md` (MIN-14); `docs/roundtables/1-embodied-ai-in-a-3d-physics.md` section 6.
- The 3D map: 3d-force-graph on three.js 0.168, one local runtime through the page's import map (`three`, `three/addons/`), VIEW-003. The page owns the frame loop: `frame3d` in `page/app/map3d/graph3d.js` draws only while something moves, `wake3d` wakes it, `AFTER` holds the per-frame hooks, one page-owned pass in the render chain (`prepare3d`, `fibers3d`, `nodes3d`), shaders linked ahead of use (`warm3d`). Glass, bloom, fibers, the label atlas and the haze of depth are the map's own.
- Figures: seventeen procedural characters in `page/agents3d.js` (`createAgent`, `MOTION`, `drawGlyph`, `eyeOf`, `orientAgent`), about 1.6 units tall; walking, eyes, bubbles and attention in `page/app/figures/`; a body given by `web_embody` (`page/app/dock/embody.js`, `figures/agents.js` `embody`); the person's mascot.
- Agent verbs on the map, declared in `src/metaform/modules/web/__init__.py`: say, go, turn, point, emote, move, push, drag, drop, take, release, see, look, select, camera, tab, open, swap, flow, physics, embody, viewing, come, capture. Each reaches the open page through `ask_page` (`POST /api/mascot`, `MASCOT_ASKS` in `web/server.py`) and answers once the page has acted. Dispatch lists them to agent roles by hand (`MASCOT_VERBS`, `EYES_VERBS` in `dispatch/__init__.py`); modules' tools are listed from their declarations at `metaform://<module>/tools`.
- The roundtable stage, `page/app/roundtable/stage.js`: a second three.js scene and renderer on its own canvas over the map, seats as figures held in typed arrays, its frame run from the map's frame (`SEATS.frame`), events read filter-first from `map.changed` kinds `roundtables:<table>`. It is the pattern for a space drawn beside the map in the page's one loop.
- Live updates: `map.changed` over `GET /api/events`, carrying `kinds`, `work_ids`, `session_ids` and `tables`; a write announces itself; handlers filter first and coalesce bursts (`page/app/live/ops.js`). No polling.
- The module contract: `Module` with `Verb`s (`effect`, `open_world`, `needs_project`, `caution`), `Tables` at `place='project'` or `'metaform'`, panes and toolbar items, `node_read`, `work_read`, `resources/prompts.xml`, a start hook, the public base only (`docs/guides/extending-metaform.md`); `modules/template` is the start of every module.
- The page's content policy already allows compiling WebAssembly (`SCRIPTS` in `web/server.py`, for the voice module's Whisper). A vendored library is an unchanged release file with its license and SHA-256 in `vendor/README.md`; `three/addons/controls/OrbitControls.js` is vendored, `TransformControls.js` is not. Node 22 is a dispatch requirement (`NODE` in `dispatch/__init__.py`), so a headless JavaScript runtime exists wherever agents run.
- The map: Metaform is `code.system.management.knowledge` (DE); the Web GUI `code.interface.graphical`; the chassis `code.framework.plugin`; dispatch `code.dispatcher.agent`; the map store `code.graph.knowledge`; the package builder `code.builder.package`. Knowledge and memory live at addresses (CTX-004, CTX-020) and reach an agent that arrives there. No element for the world exists yet.

## The design, in one page

1. **Authority (I5, WORLD-001, WORLD-003).** The `world` module owns the log and is the scene service. `append` validates kind and payload, checks `base_revision` against the entities touched, assigns `seq` inside the write, records who acted (user, agent, work, session) and announces `map.changed` kind `world:<id>`. The person's gizmo and an agent's verb write the same operation. Nothing reads the renderer to learn the world.
2. **Runtime (I4, WORLD-007, WORLD-008).** One JavaScript runtime, fold plus behaviors plus physics step, with no rendering in it, served from the module's resources: run by the page, by Node for headless checks, later by the export. The Python module folds the log too (reads, undo reversal); one fixture log proves the two folds equal. Physics is Rapier behind the host's `step` call: fixed timestep, seeded, stable insertion order, in a Web Worker, transferable buffers.
3. **Surface (I3, I11, WORLD-002).** The world is a tab of the large area; the map is one tab away. The view draws entities as instanced primitives from one typed array per field, one draw per material class, in the page's one frame loop. Edit: orbit, grid, select, primitives, gizmo, materials, spawn, undo. Play: snapshot at start, runtime changes are acts, Edit restores the snapshot.
4. **Agents (I7, I8, WORLD-009 to WORLD-011, MIN-13).** The existing figures are the bodies, the same characters; 1.6 units is 1.6 m, so the body unit is the world unit. Agents act through `world_*` verbs: `see`, `probe`, `place`, `set`, `link`, `look`, `propose`, `preview`, `commit`, `discard`, `claim`, `check`. Each answers a delta with units and frames; each call may name its `actor`.
5. **Meaning (I1, WORLD-004).** An entity's `functional_refs` tie it to addresses. Purposes, constraints, decisions and accepted exceptions live at the address as knowledge and memory and are pushed to an agent that arrives there, as the map does now. An entity that gains a purpose is promoted to an element (CTX-010) and linked. Selecting an entity shows its node; selecting a node shows its entities.
6. **Proof (I14, I15).** A purpose becomes a bounded check: the runtime runs headless from a snapshot with a seed for N ticks, states its assumptions, and is hard or advisory. An accepted exception is recorded at the address, so later agents respect it.

## Tickets

Each ticket names its node, what to do, and what done looks like. Its runtime (agent, model, effort) is chosen at dispatch by the Facilitator and Jev, never fixed here. New spec wording is drafted by the worker in `artifacts/specs-draft/`; the person approves it. Tests go into the module's test file; the new module's test files are new files, approved with this proposal (D6).

### T1. `Tab`: modules declare tabs, and the maps become tabs (WORLD-002)
Node: `code.framework.plugin`.
Do: `Tab` beside `Pane` in `src/metaform/module.py`: `id`, `title`, `description`, `icon`, one of `page`, `verb` with `arguments`, or `resource`, with `order` and `selection`; `Module.tabs`; `check_workspace` checks ids unique, the verb declared, its effect `read`, `arguments` and `selection` its own nouns; the template declares one tab; the page reads tabs from the workspace it reads panes from and draws the row above the large area (`page/app/header/`); the 2D and 3D maps become the `web` module's tabs; every key keeps its binding.
Done: a module whose tab names an undeclared or writing verb fails at import naming the module (test beside the pane checks); the template's tab shows its resource (browser test in `web/tests/test_web.py`); S, Alt+arrows, P and R bound as before.
Leave alone: `page/app/map2d/`, `page/app/map3d/`.

### T2. The `world` module: log, fold, undo, snapshot, verbs (WORLD-001, 003 to 007)
Node: `code.system.management.knowledge`; proposed Address `code.host.world` ("world host"), added to the base map by the ticket with its purpose join to Metaform, its files linked with `dispatch_link`.
Do: `src/metaform/modules/world/` from the template. Tables, `Tables(version=1)`, place `project`: `world` (world_id, revision, settings); `world_op` keyed (world_id, seq): kind, entity_id, payload as JSON, class, user_id, agent_id, work_id, session_id, base_revision, at, undoes; indexes (world_id, entity_id, seq) and (world_id, class, seq); `world_snapshot` (world_id, revision, entities as JSON). The nine kinds validated on append, an unknown kind refused and not stored. `functional_refs` on `create_entity` and `link_functional_entity`, an unresolved address reported, never dropped. `fold.py` pure: operations in, entities out. Undo per WORLD-006. The snapshot validated by revision on read, discarded when it does not match. Verbs: `world read`, `world log [class=] [after=]`, `world apply ops=<JSON>` (the one write path; refuses a stale `base_revision` naming both revisions), `world undo`. README, CHANGELOG, `resources/prompts.xml`, rows in `docs/reference/metaform-mcp-server.md`; `tests/module_tables.snapshot.json` gains the world entry only.
Done: `modules/world/tests/test_world.py`: create, transform, delete fold to one entity at the second transform; the same log folded twice is equal; a stale `base_revision` on a changed entity is refused with both revisions; an unknown kind is refused and the log unchanged; the four undo cases of WORLD-006; a corrupt snapshot reads the same as the fold; `metaform world read` on a fresh project answers revision 0; every other module works with the module disabled (`tests/test_module_combinations.py`); `map where address=code.host.world` shows the element.
Leave alone: chassis files, dispatch.

### T3. The world tab and the editor: page host, instanced view, Edit (WORLD-008's page host, I3)
Node: `code.interface.graphical`.
Do: `page/app/world/`. The host interface (read at a revision, subscribe after a revision, append, step) over `GET /api/world` and `POST /api/world-apply`, the route classed in `route_class` for the person and for agents. The subscription hears `map.changed` kinds `world` and `world:<id>`, reads only the ops after the revision it holds, once per burst. The fold in JavaScript (`fold.js`, moved into the shared runtime by T5), equal to Python's on the fixture log. The view: a scene and camera for the tab, drawn in the page's one frame loop through `AFTER`, the map keeping its small area as a swap does; entities as instanced meshes per primitive (box, sphere, cylinder, capsule, plane) from one typed array per field (position, quaternion, scale, color), sized once and regrown when the world grows, one draw per material class, no allocation per frame; the grid one shader plane; orbit camera; pick by instance id; `TransformControls` vendored from the three.js 0.168 release with its license and SHA-256; a drag coalesced into one `set_transform` on pointer up; materials (color, roughness, metalness) as `set_component`; spawn at the grid point under the pointer as `create_entity`; the undo key calls `world undo`; `window.metaform.world()` returns revision and entity ids for checks.
Done: browser test `modules/world/tests/test_world_page.py` (marker `browser`): World tab, add a box, move it with the gizmo, reload: the same transform and revision from `metaform world read`; undo reverses it; `world log` shows the person's op with `user_id`; an op appended from the CLI shows on the open page with no reload and no request while idle for 3 s; frame time (median, p95, p99) on the RTX 3090 headless and draw calls per frame recorded in `artifacts/perf/<date-slug>/` for 1, 100 and 1000 entities; the page server's idle CPU over 60 s unchanged.
Leave alone: the map's drawing, the roundtable stage.

### T4. Agent verbs in the world (I7, I8, WORLD-009 to WORLD-011, MIN-13 sections 1 to 2)
Node: `code.system.management.knowledge` (the world module); the page acts at `code.interface.graphical`; the role listings in `code.dispatcher.agent`, named in the ticket.
Do: `world see [detail=groups|items] [fov=] [camera=]`; `world probe ray=|volume=`; `world place shape= beside=<address|entity> distance=1m [facing=]`; `world set entity= transform=|component=|property=`; `world link entity= address=`; `world look [camera=]`, a picture from the actor's eyes or a named camera entity; `world cameras`. Every act answers its delta: `moved`, `turned_degrees`, `entered`, `left`, `touched`, `dragged_along`, empty lists never absent; distances as `1.4 m`; bearings with their frame (`left of your body`); targets by address and relation first, `point=x,y,z` the fallback. `actor=<body>|none|omitted` per actor-binding section 1; resolution against the observation's view frame, section 2. Agents write `act`s and only the `edit` kinds the person grants; a refusal gives the reason and the nearest alternative (WORLD-005). An actor whose last act was in the world is drawn there in its own character, and on the map once it acts there again. The verbs join the listings that reach agents: `MASCOT_ASKS` in `web/server.py`, `MASCOT_VERBS` and `EYES_VERBS` in `dispatch/__init__.py`, and any hand table left in `mcp/catalog.py`.
Done: test-host tests with no browser: `see` defaults to groups with counts and bearings; `detail=items` gives entries; a narrow `fov` sees fewer; `place beside= distance=1m` lands the entity 1 m from the surface; a unit on every distance; the body frame and the person's frame give different headings; an agent's ungranted edit refused with its alternative; `actor=none` legal on `place` and refused `invalid` on a walk; a worker session started after the change lists the verbs (`mcp/tests/test_mcp.py`).

### T5. Play and Edit, behaviors, Rapier, the tick record (I3's acceptance, I10, I11, I16, I17, WORLD-008's step, WORLD-012)
Node: `code.system.management.knowledge` (runtime, vendoring) and `code.interface.graphical` (Play and Edit on the page).
Do: the runtime as ES modules under `modules/world/resources/runtime/` (fold, behaviors, physics; no three.js), served to the page and run by Node. Rapier's enhanced-determinism build vendored as an unchanged release with license and SHA-256; the content policy already allows the compile. The host's `step`: fixed timestep 1/60 s, seeded, bodies inserted in `seq` order, in a Web Worker, one transferable `Float32Array` of transforms per step, no `SharedArrayBuffer`; two streams from the tick seed, `world` and `motion` (actor-binding section 3). Physics components: body (static, dynamic, kinematic), collider (primitive, compound convex), mass, friction, restitution, groups, sensor. Behavior library v1 as event, condition, action through `attach_behavior`: events `enter`, `leave`, `press`; conditions on properties; actions `move_to` (kinematic), `set_property`, `emit`. Play: snapshot at start; runtime changes logged as `act`; Edit restores the snapshot; "keep" writes chosen runtime changes as `edit`s. The tick record per WORLD-012, `metaform world ticks`, kept for one run; `restore(tick)` per actor-binding section 6.
Done: plate and door: in Play a dynamic body on the plate opens the door; `node runtime/check.mjs <snapshot> --ticks N --seed S` gives the same door state and the same tick record as the browser; the same seed twice gives identical worlds, in Node and on the page (`test_world.py`, `test_world_page.py`); an `act` is never undone; Edit after Play leaves the acts in the log and the world at the snapshot; frame time (median, p95, p99) and worker step time with 200 dynamic bodies on the RTX 3090 headless, in `artifacts/perf/`; reduced motion changes nothing of the simulation.
Caution: a headless GPU probe shares the person's GPU; the worker warns first and stops on their word.

### T6. Reviewable edits: propose, preview, commit, discard, claims (I9, I8's previews; WORLD-013's ghost previews brought forward)
Node: the world module and `code.interface.graphical`.
Do: a proposal is a batch of ops against a `base_revision` with its actor and reason, kept in `world_proposal`, not in the log. `world propose`; `world preview` answers before and after `see` from a named camera, the changed ids and T7's checks run on the preview; `world commit` appends the batch in one write, each op its own `seq`, refused when stale; `world discard`. The page draws a proposal as ghosts on a person-facing layer that agent cameras never render, one allowlist constant (actor-binding section 7), with its author and reason beside it. `world claim` marks entities or a box as an agent's soft claim, shown as a tint, never blocking the person. A gizmo drag stays one op, authored by the person.
Done: a proposal previewed then discarded leaves the revision and the view unchanged (browser test); a commit on a stale revision is refused; an agent's `look` frame holds no ghost; `world log` names the author and reason of a committed batch.

### T7. Checks: purposes as bounded assertions, exceptions kept (I14, I15)
Node: the world module; the check items at the entity's address, in a knowledge layer (`code.graph.knowledge` for the layer form).
Do: `world check [entity=|address=] [ticks=] [seed=]`. An assertion is a knowledge item at the functional address (layer `world_check`, LAYER-001, CTX-004): the entity, the snapshot, the seed, the ticks, the condition (`open(door) after press(plate) within 120 ticks`, `reaches(body, region)`), hard or advisory. It runs the runtime in Node and answers with the assumptions it ran under. `world accept check= why=` records an accepted exception at the address; later runs report it as accepted. A node's checks reach an agent arriving there as any knowledge item does.
Done: the plate-door check passes; detaching the behavior fails it naming the tick; an accepted exception shows as accepted, not failed; `map where address=<the door's address>` lists the check item.

### T8. Meaning on the map: entities and nodes, promotion (I1, WORLD-004's "how it shows")
Node: the world module (`node_read`) and `code.interface.graphical`.
Do: the module's `node_read` shows the entities standing for a node under `world` in `map where` and `map node` (BASE-035); on the page an entity selected shows its node in the Object tab and a node selected lights its entities; `world promote entity= address= purpose=` adds the element to the base through the map's refine path (CTX-010, VIEW-033's validation) and links it; an unresolved reference shows as unresolved; the node summary an agent gets (`node_summary_bytes`) counts the entities and names the read.
Done: `map where address=<x>` shows `world: {entities: [...]}`; selecting either side selects the other (browser test); promote makes the element and the reference resolves; a removed element leaves the reference reported unresolved.

### T9. Actor identity (MIN-3): who acted, through what, from where
Node: `code.dispatcher.agent`.
Do: `actor_instances`, `actor_bodies` and the `session_actors` binding per `docs/reference/actor-identity.md`, place `metaform`; the world's `append` resolves `actor_instance_id` and `acp_session` at commit (actor-binding section 5); `web_embody` writes the body's hold; a roundtable seat is an actor with no session.
Done: a child agent's op resolves from its own actor instance; a body handed back and retaken shows two spans; a resumed session keeps the recorded `acp_session`.

### T10. Export: a standalone playable world (I4)
Node: `code.builder.package` and the world module.
Do: `metaform world export [folder=]`: the runtime, a minimal viewer with none of the page's code, the snapshot and the assets as a static folder for any static server; `web serve` serves it locally.
Done: the exported plate-door scene plays in a bare browser from a static server; the Node check of the exported snapshot matches the browser.

### T11. The benchmark scene and the measured-need gate (I27)
Node: `code.system.management.knowledge`.
Do: the hillside settlement (tunnel, redirected stream, bridge) authored with T1 to T8 as far as primitives allow; what it cannot express is the evidence for the deferred ideas (terrain I20 to I23, generation I24, destruction I19, environment I26), each then its own proposal.
Done: the scene file in `docs/playground/`, a note of what was impossible and why, no engine code added.

## Implementation order

1. T1 and T2 together: chassis and module, no shared files.
2. T3, after T1 and T2.
3. T4, after T3; its test host first, the page acts second.
4. T5, after T3; vendors Rapier.
5. T6 and T7, after T4 and T5.
6. T8, after T3; beside T6 and T7.
7. T9, before anyone but the home's one person edits a world.
8. T10 and T11 last.

Dependencies go on the board as `after_work`. One worker per ticket; tickets sharing no file may run together within the slot limit. Each ticket's commit carries its tests and goes to the FQC as the pipeline runs now.

## Open decisions for the person

**D1. I6: object ids or Metaform addresses.** Recommend WORLD-004 as confirmed: an entity has its own id; `functional_refs` carry addresses and may be empty; T8 promotes an entity to an element when it earns a purpose. Why: an address names a functional element with a purpose join (MAP-002); making every crate an element fills the base with things that serve nothing, which the intake keeps out (CTX-001, CTX-003); every seat ranked I6 between 13th and 17th. The alternative, ids equal to addresses, costs every prop a purpose entry and turns a renamed address into a world migration.

**D2. I12: snapshots plus history, or intent operations.** Recommend the log of resolved operations as the authority (WORLD-001) with the snapshot as a cache (WORLD-007); when generators come (I24), a generated entity's `create_entity` payload carries its provenance (generator, version, seed, inputs) beside the resolved result, so a replay never reruns a generator. This keeps the table's later position (versions, inputs and resolved results recorded) inside the records already confirmed. The alternative, snapshots authoritative with history beside them, loses undo as a read of the log, attribution per change and the ordering of two clients, which WORLD-003 and WORLD-006 pay for once.

**D3. The physics engine.** WORLD-008 left it to a bake-off (MIN-8). The table's consensus is Rapier (I16, I17); the research note calls it the least disruptive first choice; the page already allows WebAssembly. Recommend Rapier in T5 behind the `step` seam, measured on the research note's table (frame time, query latency, controller stability, raycast throughput, contact quality, simulation cost, reproducibility, worker complexity, serialization fidelity); Jolt and Box3D stay possible behind the same seam. The person confirms, or asks for the bake-off first.

**D4. One body across spaces.** Recommend one character per agent: its figure stands in the world while its last act was there, on the map otherwise; `web_*` verbs stay the map's, `world_*` verbs the world's. A second body per space doubles embodiment state and the lease rules of cut 2.

**D5. A tab, not a room inside the map.** Recommend WORLD-002's tab with the map one tab away; "inspect the implementation" from an entity selects its node and shows the map tab, the research note's teleport, with no new mechanism. A world inside the force graph was rejected by the research note: the two spaces have incompatible optimization goals.

**D6. New test files.** T2 and T3 add `modules/world/tests/test_world.py` and `test_world_page.py`; approving this proposal is the ask the testing rule requires.

**D7. Node for headless checks.** `world check` and T5's headless proof run the runtime under Node 22, already required by dispatch; without Node the verb refuses with dispatch's install hint. Confirm Node as a runtime dependency of the world module.

**D8. Export now or later.** T10 is last. Say if a standalone export is wanted before checks and meaning (T7, T8).

**D9. Roundtable 6's ideas.** Kit parts, phase cards, per-user agents, replayable checks for novices and instant rough previews are the proposal of ticket `code.system.management.knowledge#a0`. This plan leaves them their seams: the behavior library is the parts kit's floor, `world check` is its replayable check, proposals are its "try it here" and "keep mine", phase cards fit workflow runs.

## What stays out, and why

- Terrain, SDF bricks, meshing, destruction, procedural generation, environmental simulation, branching by purpose, multiplayer authority: deferred by the table (I27) until the benchmark scene (T11) shows the need; each gets its own proposal with measured evidence.
- The lease on a hold, the body's named state and view cone, edge arrows, camera protection, event delivery on the next tool result: WORLD-013's cut 2, unchanged. T6 brings only ghost previews forward, because the table ranked reviewable edits 8th of 27.
- Physical-safety regulation from roundtable 1: out of scope (WORLD-013).
- Settings: none added. The fixed timestep, tick retention (one run) and the primitive set are decisions; a control is added only when the person asks for a choice.
- Polling: none. The page hears the world through `map.changed`; the fixed timestep is the world's clock, not a look for a change. Frames are never throttled or capped; performance work lowers the cost of a frame.

## Spec records this plan touches

WORLD-008 gains the engine and the worker (D3); WORLD-013 moves ghost previews into T6. Play and Edit, the behavior library, proposals and claims, checks, promotion and export need records of their own, drafted by their tickets in `artifacts/specs-draft/` for the person's approval and never written into `specifications/` by a worker.
