# Roundtable 6: proposal for the open-ended environment

Table `808d9d6c`, 2026-10-21 12:09–12:13Z. Four seats: Opus (claude/opus), Astra (codex/gpt-6-astra), Sol (codex/gpt-6.1-sol), Fable (claude/fable). Source: `mechanical-report.md` and `export.json` in this folder. Idea numbers I1–I23 are the synthesizer's (Opus); turn numbers T01–T30 point into `export.json`. Roundtable 5's ideas are cited as RT5 I1–I27 from `../5-world-representation-generation-and-simulation-explore-the-t/report.md`, the plan this proposal revises.

This is a proposal for approval. It files no tickets. Every path, record and count in it was checked against the tree at the time of writing; what could not be checked is marked as an assumption in section 9.

## 1. The question, and what the chair added

The question, as the record holds it:

> in the last roundtable we talked about this as a possibility, docs/roundtables/5-world-representation-generation-and-simulation-explore-the-t/report.md
>
> But what if it was even more open ended..  like no matter what it was the agent can come out and help the user construct things but what if we made it actually fun.. like so even a younger child could do it or someone with no experience at all...  the robot character could come out and go carte blanch..  like so you want to make a website, a game, a program.  and the robot has a canvas and works with the user kinda mocks it up and makes a plan together..  and does it in phases.  thoughts?  I think for the 3D environment it should be very advanced where even multiple AI's and multiple people can be building.,. I could even imagine each user having their own agent they control and be working togetehr to build something in 3d with physics,

The chair spoke twice. T14, after Opus's T13 on re-running checks: "yes opus.. constrained". T30, closing the table after every seat had passed: "no I mean a sandbox limited by the design..  if its a 3d game you can do anything that environment allows.. but we should make it safe somehow".

T30 settles what "constrained" means. The synthesizer read T14 as endorsing I14, a fixed parts kit the robot may not leave. T30 corrects that reading: the constraint is the design of the environment itself. Inside a 3D game, anything that environment allows is allowed. Safety is a property the environment has to have, not a list of things the robot may not build. Decision D8 in section 5 carries this.

## 2. What the table said

**No rankings were read.** The table ended at the ranking stage. `export.json` holds `rankings: []` and `rankings_counted: 0`, and the derived Borda count is zero for every idea. Weight below comes from which seats built on an idea, never from a count. The record has 30 turns: 22 kept, 2 vetoed by Jev as off topic (T10 Astra, T12 Fable), 2 chair comments, 4 passes.

### Consensus: stated by one seat, built on by at least one other, with no objection

- **I1, the pick-from-mockups loop with phase cards** (Opus T01). Fable T04 put the cards on run records; Sol T07 gave each phase a playable challenge; Astra T10, though vetoed, made the cards editable guesses. One loop for every medium; 3D is one kind of canvas.
- **I3, fun comes from agency, with three help modes** (Sol T03, T07). Fable T08 built the help modes into what the robot remembers. "a robot that instantly does everything turns making into watching"
- **I4, per-user agents with owner-bound authority, undo covering both** (Opus T01, Sol T03).
- **I8 → I9 → I10 → I11, the chain on checks.** Replayable checks re-run after every edit, a failing card turns red with "robot, fix it" and "undo my change" (Fable T04, Opus T13); a third button, "I meant to change that" (Astra T15); "does it work?" kept apart from "do I like it?" (Sol T16); a check protects only what its author set, so ownership of checks is the first multiplayer authority (Fable T17). Each seat added one link and none objected.
- **I12 and I13, sandbox and caps.** Generated code with no network, file or account access, capability limits on run records, a stop that works when the creation hangs (Opus T05, Astra T06); caps on object count, speed and simulation work, with a pause and an explanation when one is hit (Astra T19).
- **I15 → I20 → I21 → I22 → I23, the last round's convergence.** The kit is a floor, not a ceiling (Sol T20); a new part works at once in the maker's own world and a table reviews only admission to the shared kit, in the background (Fable T21, Opus T22, Astra T23, Fable T25); the robot answers at once with a rough preview labelled as not yet working (Astra T23); background results arrive beside the current creation, never over it, tied to the revision they were built against (Sol T24); slow work has a visible helper character (Fable T25).
- **I17, named parts with provenance** (Sol T07, Fable T08). **I18, the robot remembers each person and the owner controls that memory** (Fable T08, Opus T09).

### Disagreements the table left open

- **I6, region claims or declared dependencies.** Opus T01 and Fable T04 carry RT5's soft region claims forward; Astra T06 objects that claims miss shared rules such as gravity, scripts or a door circuit, so each change should show what it affects and a change to a shared rule should need agreement. Nobody answered Astra. This plan takes Astra's form (RT5 T6 revised, section 6) and files no claims.
- **I14, the fixed kit as the constraint.** Opus T18 limits what the robot builds to kit parts; Sol T20 answers that the kit must not be the product's ceiling; the chair's T30 says the constraint is the environment's design. Settled by T30: decision D8.
- **I20, when a table reviews a part.** Fable T21 wanted a table before a part enters the kit; Opus T22 said minutes of waiting kills fun; Astra T23 said agreement does not prove a part works. Fable T25 conceded: the table reviews kit admission only, in the background. Settled by the seats: N3.
- **I16, medium modules with a 2D game first** (Opus T09). Fable T12, vetoed as off topic, objected that a creation must outlive the module that made it. No other seat took the 2D-first order up. This plan does not take it: decision D9.
- **I7, phase cards as workflow run records** (Fable T04). No second seat. This plan makes phase cards tickets: decision D1.

### Single-seat ideas, with no objection

I2, "show me what you want to happen" with a visible "you decided / robot guessed" split (Astra T02). I5, a private rehearsal copy before the shared world (Astra T02). I13, runtime caps (Astra T19). I19, test one full journey before adding breadth (Sol T11). I23, a visible helper character for background work (Fable T25). All five are in the plan.

### Vetoed turns worth keeping

T10 (Astra): test the shared contract on two contrasting creations, a personal website and a bridge with physics, each surviving a change of mind midway; phase cards are editable guesses. T12 (Fable): artifacts and named parts go to project-owned storage so a creation outlives its module. Jev read both as off the table's topic. T12 is already how WORLD-001 stores the world, tables at `place='project'`; T10's two creations are a good pair for the journey test of RT5 T11.

## 3. Goal

**Who benefits.** The person who owns the project and the people they invite through a Node account, including a child or someone with no experience; and their agents, each of which needs to know what it may do and what it did.

**What they can do when it is done.** A person says what they want to make, or shows it. Their robot, the system agent in the person's own mascot body, sketches two or three ways and the person points at one. The plan is a row of phase cards they can read. The robot builds one card at a time and says "try it!". Every card keeps a check the robot replays in front of them, so a second edit cannot quietly break the first; when it does, the card turns red and the person can undo, ask the robot to fix it, or say they meant it. The robot remembers them next time. In the 3D world several people and their own agents build in one world with physics; each person's agent acts only with that person's permissions; each tries a change privately before bringing it in; what a change affects is shown before it lands. What can be built is bounded by what the environment allows, and the environment stays safe: caps below the model, grants on edits, a stop that always works.

**The earlier plan.** Roundtable 5's answer is already a plan with tickets: `../5-world-representation-generation-and-simulation-explore-the-t/proposal.md` (RT5 T1 to T11, decisions RT5 D1 to D9). Its D9 hands this table's ideas to this ticket and names the seams they fit. This proposal keeps RT5's tickets, marks each change to them and its why, and adds the tickets RT6 needs. The person approves one plan, not two: section 8, decision 1.

**The smallest increment that proves the core** is RT5 T1, T2, T3 and T5: a person places a plate, a door and a ball, plays it, reloads it, undoes it. T4 puts the robot in it beside them. T7 and N1 make it the loop with cards and checks. T9 and T6 make it shared.

## 4. What exists, by owner

Nothing of the world is in the tree. `specifications/10-world.md` (WORLD-001 to WORLD-013, confirmed 2026-10-14) is the design; there is no `world` module, no operation log, no `Tab` in `src/metaform/module.py` (it holds `ToolbarItem` and `Pane`), and no rigid-body engine in the page (`web/vendor` has three.js 0.168.0, 3d-force-graph 1.73.4 and d3-force-3d; no Rapier; `three-addons/controls/` holds Drag, Fly, Orbit and Trackball controls, not `TransformControls`). The page's content policy already allows compiling WebAssembly (`SCRIPTS` in `web/server.py`, line 115, `'wasm-unsafe-eval'`). Node 22 is a dispatch requirement (`NODE` in `dispatch/__init__.py`, line 258). A playground prototype, a room with grid parameters rather than an entity world, was set aside unreviewed on branch `codex-unreviewed-2026-10-20` at commit `8747caac` (`src/metaform/modules/web/playground.py`, 157 lines; `page/playground.js`, 194; `page/playground-surface.js`, 247; three tests). It is reference, not a base.

Owners this plan reuses, each with its path. A second owner of any of these would split truth, so every ticket below names which one it extends.

| Owner | Where | What it owns today |
|---|---|---|
| The robot | `src/metaform/modules/dispatch/__init__.py`: `SYSTEM_TASK` (line 3578), `anchor`, `system` (3637); its brief is `<system>` in `modules/dispatch/resources/prompts.xml` (line 276) with the `<mascot>` line | one system agent per project, anchored on a held ticket, talking in the chat dock |
| The robot's body | `web/page/app/figures/mascot.js` (`MASCOT`, `mascot3d`, `pushJob`, `dragJob`); setting `web_mascot` in `web/__init__.py` | the person's character on the map; the system agent speaks as it |
| Agent figures | `web/page/agents3d.js` (`GLYPHS`, `MOTION`, `BUILD`, `createAgent`, `orientAgent`, `placeAgentOnCurve`); `app/figures/agents.js` (`figures`, `helpers`, `embody`); `roam3d.js`; `walk.js` | seventeen characters, their motion, and helper figures beside their parent worker (I23 exists) |
| Agent acts and perception | `web/__init__.py` verbs `say go turn point emote move push drag drop take release see look select camera tab open swap flow physics embody viewing come capture` (lines 1145–1228) through `ask_page` → `POST /api/mascot` (`server.py` `MASCOT_ASKS`, 285; `mascot_request`, 1485); on the page `app/figures/attention.js` (`mascotEvent`, `settle`, `MASCOT_ACTS`) and `app/figures/eyes.js` (`seeFrom`, `lookFrom`, `capture`, `viewing`); listed to agent roles by hand in `MASCOT_VERBS` and `EYES_VERBS` (`dispatch/__init__.py`, 1024, 1026) | the one path by which an agent acts and sees on the page; one `Verb` declaration drives CLI, MCP tool and page |
| Render loop | `app/map3d/graph3d.js` (`frame3d`, `FRAMES`, `wake3d`, `afterFrames`, `AFTER`) | the one requestAnimationFrame loop of the 3D map; per-frame hooks run through `AFTER` |
| Layout physics | `app/views/bar.js` (`PHYSICS`, `applyPhysics`); 3d-force-graph and d3-force-3d in `web/vendor` | force-layout presets; not a rigid-body engine |
| A scene beside the map | `app/roundtable/stage.js` (`TABLE`, `SEAT` typed arrays, `VIEW` with its own scene, camera and renderer on its own canvas, `stageFrame`), run from the map's frame through `SEATS.frame` (`app/figures/bubble3d.js`, 601) | the precedent for a space drawn beside the map in the page's one loop: a second scene and canvas, no second loop, the map sunk behind, figures and bubbles reused |
| Camera | `app/camera/fly3d.js` (`fly3d`, `workShot`, `MEET`) | the person's 3D view |
| Live events | `app/live/ops.js` (`listen`, `TOPICS`), `app/live/stream.js` (`changed`); `server.py` `events` (1320) and `events.listen('web', server.changed)` (4147) | one EventSource per page; `map.changed` relayed across processes with the tables, ids and kinds it concerns |
| Chat and its canvas | `app/dock/*`; `web/apps.py`, the MCP Apps host (`/api/mcp-apps`, `/api/mcp-app`, `/api/mcp-call`); `dispatch_attach`, `/api/attachment` | a tool's view shown in the thread in a sandboxed frame with an opaque origin and a content policy (MCP-037); pictures attached to a chat |
| Tickets and board | `modules/map/__init__.py` `WORK_READS` (`add`: `title task kind condition after_work epic agents board agent model effort held links`), `op=plan/step/done`; VIEW-035, VIEW-037, VIEW-040 | a ticket is a map element's work record: a light on its node, a card with a glyph, dependencies, an epic |
| Agents on tickets | `dispatch/__init__.py` (`start_runner` admission, `HELPER`, `dispatch_helper`); `modules/orchestration` (planner, implementer, verifier, reviewer, architect, designer, researcher, `role_creation`); `modules/agents/roles.py` | who builds a phase, with which expertise, within which limits |
| Memory and decisions | `modules/memory` (entities, observations, relations at nodes; page `app/memory/manage.js`); `src/metaform/jev.py` (typed decisions cached at addresses); `web/hints.py`, `web/view.py` (per account) | what is remembered, where, and for whom |
| Accounts | `modules/node` (`authstore.add_account`: owner, member; setting `node_member_dispatch`) | who may join and what a member may start; no child role |
| Voice | `modules/voice`, `modules/elevenlabs` | the robot heard, and its replies spoken |
| Roundtables | `modules/roundtables` with the stage above | a table on a question, its one-line verdict possible |
| Builds and variants | `web/builds.py` (BASE-060), `metaform web serve` (PROJ-019), `modules/packet` | how a creation leaves Metaform today |
| Identity design | `docs/reference/actor-identity.md` (MIN-3), `docs/playground/actor-binding.md` (MIN-13), `docs/measurement/spatial-reference-protocol.md` | the actor rows, the binding on each call, the record every op carries; written, not built |

## 5. Design decisions

Each compares the adequate approaches and says why one was chosen. These are engineering choices; section 8 lists only what the person must decide. Where RT5's proposal already decided the same question, this plan says so and does not decide it twice.

**D1. A phase card is a ticket.** Alternatives: a workflow run record per card (I7; RT5 D9 says "phase cards fit workflow runs"); a new card record. A ticket already is a map element's work record with a title, a task, a why, dependencies (`after_work`), a group (`epic`), a board column and a card, a glyph and an agent, held messages, a light on its node and a figure that walks to it (VIEW-035), dispatch to start a worker on it and an assessment to judge it. "A stuck phase shows on the board as owned, unfinished work" is what an open ticket in Doing already is. A run record is for a procedure carried between agents; wrapping a ticket in one stores the same thing twice. Cost: nothing new to store. What a ticket lacks is a check that can be replayed, which T7 adds beside it.

**D2. The robot is the system agent in the mascot's body.** Alternatives: a new "robot" agent kind. The system agent is already the person's, already talks with them about anything in the project, already speaks as their mascot (`web_mascot`), is already the Liaison of the roles chain, and the chat already offers bodies to agents. The loop is a change to its brief, product text in `dispatch/resources/prompts.xml`, and to what the page shows of it, not a second agent.

**D3. A mockup is a card the person picks.** Alternatives: a picture attached to the chat (`dispatch_attach`); a view of the chat's MCP Apps host (`apps.py`), a small HTML sketch in a sandboxed frame whose pick comes back as a tool call; for the world, a ghost of the idea in the scene. Chosen: the MCP Apps view for anything that is a page, a game screen or a program, because the pick is one click and reaches the host as a call; a picture as the fallback when the sketch is static; and in the world, the ghost previews RT5 T6 brings forward from WORLD-013, labelled as the idea (I21). No new surface: the thread the person already reads.

**D4. The world is RT5's `world` module, authority in Python, one write path.** RT5 T2 as proposed: tables at `place='project'` (WORLD-001), `world apply ops=<JSON>` as the one write path, the fold pure in Python and again in the runtime's JavaScript with one fixture log proving them equal. This plan changes one thing in T2: the record columns of `docs/playground/actor-binding.md` §5 go into the first migration (D10).

**D5. The simulation runs in the page host behind `step`, as a worker, from a seed.** RT5 T5 as proposed: the runtime as ES modules under the module's resources, Rapier's enhanced-determinism build vendored, a fixed timestep, seeded, in a Web Worker, run by Node for headless checks. RT5 D3 asks the person to confirm Rapier; this plan seconds it and adds nothing to that decision. This plan changes one thing in T5: runtime caps from the start (I13).

**D6. Building together shares edits first; shared live physics comes later.** Alternatives: one simulation host from the first multi-person ticket; or no sharing until a Node host exists. Edits are already one authority in D4, and RT5 T3's subscription makes every open page apply the ops the server broadcasts, so two people build one world at once with no new mechanism. Each person's physics runs locally from the same log, so Play is each person's own until a world is played together, when one `step` must run in one place (N4). RT5 I11 and I27 deferred multiplayer authority until demanded; RT6 asks for people building together, which the log gives at once, and for playing together with physics, which N4 gives after T6 and T9 are in use.

**D7. A check is a recorded scenario on the phase card, replayed by the host.** RT5 T7 makes a check a knowledge item at the entity's address: snapshot, seed, ticks, condition, hard or advisory, with accepted exceptions. RT6 keeps that item and changes three things: the check is recorded from a Play the person just had, so the robot can perform it in front of them and replay it (I8); it carries the phase card's work id, so the card turns red when it fails; and it is re-run on the event of an edit that touches its entities, a burst coalesced into one run, never on a timer. The accepted exception becomes the person's button, "I meant to change that" (I9); taste is never a check (I10); a check is its author's (I11).

**D8. Constrained means a sandbox limited by the design.** From the chair's T30. What can be built is whatever the environment's own rules allow: the nine operation kinds, the behaviour library, the parts that exist; nothing else is forbidden by name. The kit is a floor (I15) and grows by demonstration and the owner's word (I20). Safety is built below the model, where RT1 and WORLD-005 already put it: behaviours are data from a fixed library, so nothing generated runs as code until scripting arrives, and when it does it runs in a worker with no network, file or account access and a capability list on the run record (I12); runtime caps pause the world and say why (I13); edits need a grant and acts are logged (WORLD-005); undo covers the person's and the agent's edits alike (I4); a stop the person can always reach (WORLD-013, cut 2). The parts kit of I14 survives as one rule: a part enters the shared kit with the owner's word.

**D9. One world runtime; no 2D game module.** Opus I16 would ship a 2D game module first. The 3D world is the environment the question names, its design exists, and a flat world is a camera and a constraint on the same runtime, not a second module with a second check and export. A flat mode is added when a creation asks for it.

**D10. The actor columns go into the first migration.** `docs/reference/actor-identity.md` §6 and `docs/playground/actor-binding.md` §5 say the op-log record has to carry `actor`, `actor_source`, `session`, `acp_session`, `run` and the two clocks from its first migration, because adding them later means a migration and a re-run of everything measured. RT5 T2 lists `session_id` only and leaves resolution to T9. This plan writes the columns in T2 and lets T9 fill them. Nothing in T1 to T7 depends on more than one account.

**D11. The world's surface is RT5 T1 and T3: a tab of the large area, drawn in the page's one loop.** RT5 D5 chose a tab over a room inside the map, as WORLD-002 specifies; this plan accepts it. The roundtable stage shows the shape: its own scene and canvas beside the map, its frame run from the map's loop, no second requestAnimationFrame. A world inside the force graph was rejected by the research document because the two spaces have incompatible optimization goals.

**D12. The agent verbs are RT5 T4's `world_*` verbs, and one body crosses the spaces.** RT5 D4 keeps `web_*` verbs the map's and `world_*` verbs the world's, with one character per agent standing wherever its last act was. This plan accepts both. The robot acts in the world through `world place`, `world set` and `world link` (edits, under grants) and sees through `world see` and `world look`; the in-world acts of cut 2, hold, drop and throw (`actor-binding.md` §1), come with the kit's demonstrations (N3), when the robot has to show rather than place.

## 6. Where this changes roundtable 5's plan

RT5's `report.md` gave the order; RT5's `proposal.md` turned it into T1 to T11 and D1 to D9. Neither cites this table, which ended after both were written. The changes below are against the proposal. A row that says "kept" means a builder works from RT5's ticket text as it stands.

| RT5 | Change | Why |
|---|---|---|
| T1, `Tab`: modules declare tabs, the maps become tabs | Kept | WORLD-002 as confirmed; RT5 D5 |
| T2, the `world` module | Kept, plus the record columns of `actor-binding.md` §5 in the first migration: `actor`, `actor_source`, `at_wall`, `at_sim`, `session`, `acp_session`, `run`, the two `spend_seq` watermarks; filled by T9 | A column added after records exist costs a migration and a re-run of every measured trial (D10) |
| T3, the world tab and the editor | Kept. Its subscription is what lets two pages share one world in T6 | The ops reach every open page already |
| T4, agent verbs in the world | Kept. Order: after T5 rather than before it, so the robot's first act is to show the plate-door in Play. T4 and T5 share no file and may run together within the slot limit | The first done-check is the plate-door; a robot that can see but not play has nothing to show |
| T5, Play and Edit, behaviours, Rapier, the tick record | Kept, plus runtime caps (I13): object count, body speed and step time per tick; at a cap the world pauses and the robot's bubble says which cap and what reached it, one line | Safe parts combine into unstable machines; one person's experiment must not freeze another's session (Astra T19; the chair's T30) |
| T6, reviewable edits: propose, preview, commit, discard, claims | Revised. A proposal is a private rehearsal the author can play before it lands (I5); before commit the page shows what it affects, the entities and the shared rules such as gravity or a behaviour another check depends on, and a change to a shared rule waits for the owner's word (I6, Astra); a proposal built against revision R is rechecked by T7 when the log has passed R (I22); claims are dropped | Region claims miss shared dependencies; nobody at the table answered Astra |
| T7, checks: purposes as bounded assertions, exceptions kept | Revised per D7: a check is recorded from Play and replayable in front of the person; it carries the phase card's work id and turns the card red; re-run on the event of an edit touching its entities; three answers on a red card, "Robot, fix it", "Undo my change", "I meant to change that", the last owner-only and the form the accepted exception takes; taste apart from checks, kept as preferences; a check is its author's, a guest's proposed check shows grey | RT6 I8, I9, I10, I11, I19 |
| T8, meaning on the map: entities and nodes, promotion | Kept, plus parts: "name this" on a selection stores the ops that make it relative to an anchor, promotes it to an element with purpose and provenance, and the robot offers "use your <part>"; placing a part replays its ops as one edit group (I17) | A saved experiment the robot can reuse is where the map earns its place (Fable T08) |
| T9, actor identity | Kept, plus each account's own system agent and mascot, the hover line naming the owner, a member's agent acting with that member's permissions, undo covering a person's and their agent's edits alike (I4) | "each robot should visibly belong to its person" (Sol T03) |
| T10, export | Kept, last | RT5 D8 |
| T11, the benchmark scene | Kept, plus the journey test of I19 (a novice makes something playable, leaves, comes back, changes it, invites a helper) and Astra T10's pair, a personal website and a bridge with physics, each surviving a change of mind midway | A polished first generation proves little if the second edit breaks it |
| RT5 D9, "phase cards fit workflow runs" | Tickets, D1 | A ticket already is the card, the light, the owner and the board |
| Order: T1+T2, T3, T4, T5, T6+T7, T8, T9, T10+T11 | T1+T2, T3, T5, T4, T7, N1, N2, T9, T6, T8, N3, T10, T11, then N4 and C1 if the person wants them | Play before agents; the loop before sharing; identity before anyone but the owner edits (RT5's own rule) |

## 7. Plan, in implementation order

Each ticket leaves something working. Dependencies come first. RT5's tickets T1 to T11 are built from RT5's text with the changes of section 6; the tickets below are the new ones. Every ticket carries these rules from `CLAUDE.md` and the records: changes travel on the event bus and handlers filter first, never on a timer; hot data in structure-of-arrays typed arrays, zero allocation per frame, requestAnimationFrame only, cheaper frames never fewer, with frame time (median, p95, p99) and `renderer.info` draw calls measured on the real GPU before and after; the map never idles; no new setting, key or control unless the person asks for a choice; the ticket's resolution names what it removed; new spec wording is drafted in `artifacts/specs-draft/` for the person's approval, as RT5's proposal has it; knowledge learned is kept as memory at the ticket's node. Front-end work goes to Claude; a spelled-out backend ticket may go to Codex at High or above; nothing below Medium. Tests go into the module test files RT5 D6 approves; the new tickets add no test file.

1. RT5 T1 and T2 (with the columns), together: chassis and module, no shared files.
2. RT5 T3.
3. RT5 T5 (with the caps) and RT5 T4, together.
4. RT5 T7, revised.
5. N1, the robot's loop.
6. N2, the robot remembers each person.
7. RT5 T9, revised: before anyone but the owner edits a world.
8. RT5 T6, revised.
9. RT5 T8, revised, with parts.
10. N3, the kit grows.
11. RT5 T10 and T11, the latter with the journey test.
12. N4 and C1 only if section 8 says so.

### N1. The robot's loop: show me, pick a mockup, phase cards, build one, try it

- **Node:** `code.dispatcher.agent` (the system agent's brief) and `code.assistant.navigation` (its body).
- **Why:** the question's core: a canvas, a mock-up, a plan made together, phases, fun. Each instruction in the brief carries its reason, so the agent can judge the cases the words do not name.
- **Behaviour:** product text in `<system>` of `modules/dispatch/resources/prompts.xml`. On a request to make something the agent first asks to be shown ("show me what you want to happen": in the world the person places and moves things and the agent reads `world log class=edit` and `world see`) or offers two or three mockups, D3, each a card the person picks by one click; the card is a view of the chat's MCP Apps host declared by the world module (a tool with `_meta.ui.resourceUri`) whose pick comes back as a tool call, or a picture attached with `dispatch_attach`. The pick files one epic ticket for the creation at its node and one ticket per phase with `map_work op=add`: title, task and its why, `after_work`, `epic`, the planned check in words until T7 records it, and in the task which parts the person decided and which the robot guessed (I2). It builds one phase at a time: itself for a small step, a dispatched specialist for a large one, helpers as the visible characters they already are (I23). When a phase passes its check it says "try it!" and starts Play. Each phase's reply offers the three help modes in words, "make it with me", "show me how", "do this bit for me", never as a control (I3). While a long build runs it answers at once with a rough ghost of the idea in the world, RT5 T6's preview, labelled "this shows the idea; it isn't working yet", until the build lands (I21). Background results arrive beside the current state with "try it here" and "keep mine", never over what changed meanwhile (I22). A plan read aloud goes through the voice module as replies do today.
- **Depends on:** RT5 T7 revised, RT5 T4.
- **Done-check:** with the fake ACP agent scripted: a request produces two or three mockup cards; a pick produces an epic with at least two phase tickets, each with task, why and a check; the first phase is built and the world enters Play; the journey of I19 scripted as far as "leaves and returns": the second visit finds the epic and continues it; a reviewer reads the brief and finds every point above with its why.
- **Expertise:** prompt text by the owner of the Liaison and Planner briefs; Claude for the cards. High.

### N2. The robot remembers each person, and the owner controls it

- **Node:** `code.store.memory` and `code.service.decision`.
- **Why:** "a returning child is greeted by a robot that remembers what they built, not a blank canvas" (I18).
- **Behaviour:** preferred help mode, vocabulary and past builds are observations on one memory entity per account, joined at the project's root and at each creation's node; the greeting on return names the last build and uses the help mode, one line; with Jev on, `pick_one` decides the help mode from the person's last replies and the decision is cached at the node (`jev.py`); the owner views, exports (packet) and deletes a person's entity from the memory pane; nothing is kept for an account that asked not to be remembered.
- **Depends on:** N1.
- **Done-check:** a returning account is greeted with its last build; deleting the entity makes the next greeting blank; the export holds the observations.
- **Expertise:** `memory_query_engineer`. Medium.

### N3. The kit grows: demonstrated behaviours, admission by check, the table in the background

- **Node:** `code.coordinator.discussion` and the world module's node (`code.host.world`, added by RT5 T2).
- **Why:** the kit is a floor (I15); a new part must work at once and review must never make a child wait (I20).
- **Behaviour:** a person demonstrates a behaviour the library lacks; the robot proposes it as a rule in the library's form, working at once in the maker's own world. Offering it to the project's shared kit runs its checks (T7) and, when the owner asks, a roundtable on its rule and check through the roundtables module, in the background; the stage says "the robots are talking about your idea" and the verdict lands as one line. The owner admits it: the one rule that survives of I14. "Peek inside" on a part shows its ops and rule as text. The in-world acts of cut 2, hold, drop and throw, come here, so the robot can demonstrate a part rather than place it.
- **Depends on:** RT5 T8 revised, RT5 T6 revised.
- **Done-check:** a demonstrated behaviour is proposed, works in the maker's world, is offered, its check runs, a table opens in the background and its one-line verdict shows; the owner admits it; peek inside shows the rule; the robot throws the ball onto the plate and the door opens.
- **Expertise:** Python and prompts; `character_motion_engineer` for the acts. High.

### N4. Shared live play: one simulation for a world played together

Only after T6 and T9 are in use and the person asks for it (section 8, decision 3).

- **Node:** `code.host.world`.
- **Behaviour:** the runtime of RT5 T5 runs under Node as a process the world module starts and stops on the chassis lifecycle; it is the one `step` for a world people play together; pages render its state, interpolated, and send acts to it; the page host stays for solo play, rehearsal and checks; a reconnect resumes from the host's tick.
- **Depends on:** RT5 T6 revised, RT5 T9 revised.
- **Done-check:** two browsers see the same ball roll from one throw; a reload resumes at the host's tick; frame-time p95 unchanged.
- **Expertise:** `embedded_engine_module_engineer`. Max.

### C1. Child accounts and content filtering

Only if section 8, decision 2, says now.

- **Node:** `code.server.hosting`.
- **Behaviour:** a `child` account role that cannot publish, invite or change grants; the owner controls who joins; chat and generated text pass a filter; the run record lists what a build may reach (I12).
- **Done-check:** a child account cannot invite; a filtered phrase is blocked in chat; the run record lists its capabilities.

### Later, when a creation needs it

Scripting in a sandboxed worker beyond the behaviour library (RT5 I10, I12); terrain, generation, destruction and environmental simulation (RT5 I19–I26, gated by RT5 T11); a flat world mode (D9).

## 8. Open decisions for the person

RT5 D1 to D8 stand as RT5's proposal states them; this plan adds nothing to them. Three decisions are this table's.

1. **One plan or two.** (a) Approve this plan as the one plan: RT5's T1 to T11 with the changes of section 6, then N1 to N3. (b) Approve RT5's T1 to T5 as written now and take this plan's changes as amendments after. Consequences: (a) puts the actor columns into T2's first migration and the caps into T5 from the start, each cheaper now than as a migration or a retrofit; (b) starts a day sooner and pays those costs later. Recommendation: (a).
2. **Children now, or later.** C1 adds a child role and content filtering. Recommendation: later. Nothing in T1 to T11 and N1 to N3 publishes or invites; caps, grants and undo already cover a child building beside the owner on the owner's account; a child role brings obligations about accounts and filtering that deserve their own decision.
3. **Shared live physics.** N4 puts one simulation in a Node process so a world can be played together. Recommendation: after T6 and T9 are in use and show the need. Building together needs no shared simulation; playing together does.

## 9. Record and verification notes

- Every file path, function name, line number, verb list, table and record id above was checked in the tree at `3914944e` on 2026-10-21, after the worktree was brought level with main; RT5's proposal landed on main at that commit while this one was being written, and section 6 was rewritten against it.
- The MVP build plan of 13 October 2026 and its MIN items (MIN-2, MIN-3, MIN-7, MIN-8, MIN-12, MIN-13, MIN-14, MIN-29) are named by `specifications/10-world.md` and the two identity documents, but the plan itself is not in the tree. Assumption: MIN-2, landing `land-main-wip-2026-10-14`, is done, since the branch exists and main has moved past it; the identity documents said they were blocked on it.
- `.test.mjs` files exist under `web/tests`; how they run was not verified. CI runs Node for `scripts/build_map_view.mjs`, and Node 22 is a dispatch requirement, which is the basis for the headless runs of RT5 T5 and T7.
- The RT6 roundtable memory at `code.system.management.knowledge` names a `report.md` for this table that was never written; this proposal is the table's outcome document.
