# World System Specification

**State:** draft, 2026-11-05. Written by Claude (Opus 5.5) at the owner's direction. The owner has not reviewed it.

This document specifies the world system: the world server, its worlds, and how people and agents build inside them. It is separate from `TOPOGEE-SPEC.md`. The specification is the system that can build any in-game machine. It does not specify any machine.

## How to read this document

Every requirement carries one status:

- **Decided:** the owner stated it. The source gives the owner's words.
- **Proposed by the owner:** the owner suggested it ("could", "can") and has not confirmed it as final.
- **Proposed:** an agent proposed it, with its reason. The owner has not confirmed it.
- **Assumption:** the owner stated it while exploring and has not decided it.
- **Open:** the owner must decide it. Section 13 lists each one with a recommendation.

Owner sources are from the session of 2026-11-04 and 2026-11-05 unless another source is named. `world-ideas` means `docs/world-ideas.md`. "The brief" means the owner topic brief in `docs/roundtables/session-20261104-24c67015/review-evidence.md`.

This document contains no analogies. Words such as "must" apply to the implementation.

## 1. Scope and separation

**W-1.1** The functional map is an engineering tool for building the system. It has no role inside a world. The world system never reads or writes the functional map, and players never extend it.

**Status:** Decided. **Source:** "The functional map itself can be used to develop the system, it doesnt work as a ingame tool."; "we are not seeking to have players expand our internal specification and blueprint we have in the form of our functional map we use as an engineering tool.. that would be the wrong approach".

**W-1.2** The link record between functional addresses and world entities (roundtable P4, P7 and L-33) does not apply to in-game entities. The world server's own source code takes an intake like any other project.

**Status:** Proposed. **Reason:** W-1.1 removes the purpose of that link. The second sentence follows from "can be used to develop the system".

**W-1.3** The world server is written in Rust, uses Bevy and stores world data in LadybugDB. The client is a thin Three.js client. One private install serves a group of friends.

**Status:** Decided for the server and the install. The Three.js client is Proposed by the owner: "I was proposing a threejs thin client as bevys renderer". The client options are Open (D-W9). **Source:** the brief: "World server (Rust, LadybugDB + Bevy) · UI (Three.js)"; "One private install shared by a group of friends". world-ideas: "Three.js as a thin client".

**W-1.4** The world system needs its own MCP server, built custom and inspired by metaform. The Node functional map server is for developing the system; it cannot serve the system itself, because agents must be able to blueprint their features, and the functional map's namespace setup does not support that.

**Status:** Decided. **Source:** "our map server isnt going to be able to run in node for the game.. the issue is that we need to allow agents the ability to blueprint their features and the base functional map and its namespace setup wont work for that so our node based mcp server is good foe developing the system, but wont work for the systems mcp server we came to the realization that we will need to make something custom that is inspired by metaform" (2026-11-05). What a feature blueprint holds and how agents write it are not specified yet; W-5.3 and W-5.5 describe the closest parts so far. **Reconsidered by the owner on 2026-11-06, not yet settled:** "I might have been wrong saying we need to make one specifically for topogee.., what I think we do need to allow if for agents to build their own metaform map to describe whatever it is they intend to build and give them ownership of their own metaform". See `TOPOGEE-SPEC.md` section 11, collaboration.

## 2. The void and the world

**W-2.1** A world starts as the void: voxel-addressable space with an invisible floor, no materials, no items and no rules.

**Status:** Decided. **Source:** "there is a floor you cant see but you are standing on something"; "my default there is no materials, there is no rules.. there is the void"; "the void is voxel based (addressible) but no items are defined".

**W-2.2** A world has the vertical limits of Minecraft Java Edition 1.18 and later: build height from y = −64 to y = 319, 384 blocks. The invisible floor is at y = −64, the bedrock level.

**Status:** Decided for "the same limits as MC for height and bedrock". The version and the floor position are Proposed. **Reason:** 1.18 is the current Minecraft height range. The owner placed the floor where bedrock is.

**W-2.2a** In a void, the spawn point is x = 0, z = 0, standing on the invisible floor: the occupied cell is y = −64. A world's spawn point moves only when the admin sets it, or when the world's generator reports one through an output port (W-10.1).

**Status:** Proposed by the owner for the void spawn: "in the void a system admin spawns in the void at x=0 z=0 at y-64 right?" The rule for moving the spawn is Proposed. **Reason:** Minecraft searches near the origin for a surface. A void has no surface, so the origin on the floor is the only defined point. A generator is content, so it reports a spawn and does not set one in the core.

**W-2.3** A world without a terrain generator stays a void. No chunk data can be written to it.

**Status:** Decided. **Source:** "without a terrian a world is a void, no chunk data can be written".

**W-2.4** A world consists of three kinds of content: voxels, imported 3D objects and particles. Three systems act on it: a physics system, a particle system and WASM code.

**Status:** Decided. **Source:** "the world is made of 3 things, voxels, imported 3d objects, and particles.. the world itself uses a physics system, a particle system, and the wasm itself."

**W-2.5** The world core supplies only the void, the three content kinds, the three systems, the bus and the host interface (section 7). Every material, item, rule, generator and machine is content built on that core. Content never requires an adjustment to the core.

**Status:** Decided. **Source:** "the server itself is the void and the simulacrum can be built ontop in a safe way that doesnt require changing the system core".

## 3. Chunks, regions and storage

**W-3.1** The world divides into chunks and regions and encodes them in a raw, efficient form.

**Status:** Decided. **Source:** "world uses chunks and regions. uses a raw and efficient approach to encode the chunks and regions".

**W-3.2** A chunk is a 16 × 16 column of the full height, stored as 24 sections of 16 × 16 × 16 voxels. A region is 32 × 32 chunks in one file.

**Status:** Proposed. **Reason:** these are Minecraft's sizes, which W-2.2 already follows. They make Minecraft-like content (W-12.1) map one to one.

**W-3.3** A section stores a palette of distinct cell values and a bit-packed index for each voxel. An empty section stores nothing. A region file holds an offset table and one compressed record per chunk.

**Status:** Proposed. **Reason:** a void world then costs no storage. A section with one material costs one palette entry.

**W-3.4** A voxel cell holds a material reference or nothing. Each voxel subdivides into an 8 × 8 × 8 grid that shape points snap to. A code block (W-6.1) is an entity. Its voxel coordinate and its code module instance are components of that entity.

**Status:** Proposed for the cell fields and the code block. The 8 × 8 × 8 grid is an owner idea in world-ideas ("Every block is an 8×8×8 grid that points snap to").

**W-3.5** Each world stores entities, ports, links, manifests and intent records in its own LadybugDB database. Region files hold voxel data. Code modules and imported assets are stored once, keyed by the hash of their contents.

**Status:** Proposed. **Reason:** LadybugDB is a graph database, and section 5 makes the world a graph of entities and links. Rust stores blobs in LadybugDB reliably (world-ideas, Tested). Content keys come from an agent suggestion in world-ideas.

**W-3.6** Particles are simulated and never saved.

**Status:** Proposed. **Reason:** particle counts are high and their state is short-lived. A code module that needs a lasting effect writes voxels or spawns entities.

**W-3.7** The world server keeps a chunk loaded while something holds a load ticket on it. By default, only players hold tickets, within the simulation distance. The admin can hold tickets and can grant the ticket handle to code blocks, links or agents (W-7.4).

**Status:** Proposed. **Reason:** load tickets are how Minecraft keeps chunks loaded, and `/forceload` is an admin privilege on them, not a base capability. A grantable handle lets a world add ticket sources as content, with no change to the core.

## 4. Entities

**W-4.1** Every imported object, creature, NPC and avatar is an entity with a persistent id that the world server mints. The Bevy `Entity` value is a runtime handle only and is never stored.

**Status:** Proposed. **Reason:** Bevy reuses `Entity` values after despawn and restart (roundtable P2, P4). Graph links (W-5.4) must survive both.

**W-4.2** An imported object is an asset with a mesh and colliders. An instance of it is an entity with a transform and a physics body. A joint (W-4.4) can attach an instance to another entity, including a code block. The builder chooses where an instance attaches. Attaching it to a code block lets the code block's ports connect to it directly.

**Status:** Proposed for the first three sentences. The builder's choice is Decided. **Source:** "not that it has to be its a design choice because it allowed the bus to be connected directly".

**W-4.3** Imported objects load through Bevy's asset system, in the formats it supports, such as glTF 2.0.

**Status:** Proposed. **Reason:** Bevy already loads 3D assets. The world system does not need its own importer.

**W-4.4** The world system uses the physics engine's bodies, colliders, joints and materials, and Bevy's animation system. It defines none of its own. The world needs at least these kinds of capability:

| Kind | Used for |
|---|---|
| Dynamic, kinematic and static bodies | Moving parts, driven parts and fixed parts |
| Colliders with physics materials | Contact, friction, bounce and weight |
| Joints with limits and motors | Parts that rotate, slide or connect, driven by code |
| Continuous collision detection | Fast bodies |
| Ragdolls built from joints | Creatures and NPCs under physics |
| Skeletal animation | Creatures, NPCs and avatars |

**Status:** Proposed. **Reason:** the physics engines in D-W1 supply all of these except skeletal animation, which Bevy supplies. The engine choice decides their exact definitions.

## 5. The world graph

The world graph holds the functional specification of each entity in a world. Each entity carries a manifest component: its ports, the `goal` and `function` of each port, and a `description` (W-5.3). Links between ports are the edges of the graph (W-5.4). A user writes how an entity must work (W-5.5). An agent builds the entity from that specification and tests it in the world. The agent's task context is selected from the world graph (W-5.6).

The world graph uses the metaform technique. Each node is a record keyed by an entity id, and it holds that entity's components. In the functional map, the namespace address is the entity id (`TOPOGEE.md` section 2). In the world graph, the world server's entity id (W-4.1) takes that role. Players build on the world graph and never on the functional map (W-1.1). Each world stores its graph in its own LadybugDB database (W-3.5).

**W-5.1** The world system has its own graph technique, modeled on the metaform technique. Each entity in a world is grounded by its entity id, not by a namespace address.

**Status:** Decided. **Source:** "this game world needs its own approach that uses a metaform like technique and graph associations"; "the namespace is now grounded against objects in a world that have entityid's".

**W-5.2** An entity carries its own graph edges: its expected inputs and outputs, its functional intent and a written description.

**Status:** Decided. **Source:** "objects ingame which have wasm code to carry their graph edges instead as expected input and outputs, functional intent, and a written spec type descriptions".

**W-5.3** Each code module and each imported asset carries a manifest. The manifest declares each port with these fields:

| Field | Content |
|---|---|
| `name` | The port name, unique within the manifest |
| `intent` | `inbound`, `outbound` or `two-way`, relative to the entity (R-3.6) |
| `type` | A WIT type (W-7.1) |
| `goal` | Why the entity needs or offers this port |
| `function` | What crosses the port, as one fragment |

The manifest also holds a `description`: the written specification of the whole entity.

**Status:** Proposed. **Reason:** `goal`, `function` and `intent` keep the meaning of the functional map's want fields (R-3.6), so an agent reads both graphs the same way. WIT is the WebAssembly Component Model's type language. It leaves port types open to content: records, lists, strings and variants as well as scalars.

**W-5.4** A link connects an `outbound` port to one or more `inbound` ports, or one `two-way` port to another. An endpoint is an entity id plus a port name. The world server refuses a link between ports of different WIT types.

**Status:** Proposed. **Reason:** the type check gives a builder an error at connection time, not at play time.

**W-5.5** A user records intent for how an entity works. An agent builds the entity from that intent. The intent record stays with the entity.

**Status:** Decided for the first two sentences. **Source:** "allows a user to record their intent on how an object works so that an agent can build that solution as a game object". The third sentence is Proposed.

**W-5.6** An agent's context for a task comes from the world graph: the entities the task concerns, their ports and links, their descriptions and their intent records. How that context is selected and delivered is not specified.

**Status:** Open (D-W10). **Source** for the need: W-11.2, "to have access to contextual knowledge based on the task". W-11.6 applies: the context must be brief and targeted.

## 6. Code blocks

**W-6.1** Every block can be a computer. A block holds a WASM module instance with its own state, a bus connection and inputs and outputs. A block can control other entities in the world, including an NPC.

**Status:** Decided. **Source:** "every block is a computer.. it has a bus, it has IO, and it can be tied to things ingame. a nearby block can be places and used to control an NPC."

**W-6.2** A block's code is invoked on events only: a message on an input port, a timer it subscribed to, or a sensor event. A block without events costs nothing.

**Status:** Proposed. **Reason:** an agent suggestion in world-ideas ("Give blocks events, not constant ticks"). It scales to worlds where most blocks are idle.

**W-6.3** Each invocation has a fuel budget, a memory limit and a limit on messages sent. A module that exceeds a limit fails that invocation only, and the world server disables its binding and records the fault.

**Status:** Proposed. **Reason:** the owner requires that content not harm the core (W-2.5). Wasmtime fuel metering gives a deterministic instruction budget in Rust. The limit values are Open (D-W6).

**W-6.4** Code that an agent generates is not a safety risk in this design.

**Status:** Decided. **Source:** "unlike their approach generated code isnt a safety risk in our design". **Reason**, Proposed: generated code runs only as a WASM module, under the limits of W-6.3, and reaches the world only through the host interface (W-7.1).

## 7. The host interface

**W-7.1** The host interface is the only way code reaches the world. It is a set of WIT interfaces in semantically versioned packages. A code module is a WebAssembly component. It imports the host interfaces it uses, at the versions it targets, and the world server provides only those imports.

**Status:** Proposed. **Reason:** the WebAssembly Component Model is the standard for typed, versioned host interfaces, and Wasmtime implements it. A component reaches only what it imports, which is the WASI capability model. W-2.5 makes this interface the boundary of the core.

**W-7.2** The host interface covers at least these kinds of capability. WIT interfaces define them.

| Kind | Used for |
|---|---|
| Ports | Sending and receiving port messages |
| State | The instance's own lasting state |
| Sensors | Raycasts, contacts, proximity and attached devices |
| Actuators | Forces, impulses, joint motors and kinematic targets |
| Voxels | Reading and writing cells |
| Particles | Starting and ending emitters |
| World parameters | Reading and adjusting gravity and other physics parameters |
| Timers | Delays and periods |

**Status:** Proposed. **Reason:** content of W-12.1 and W-12.2 needs each kind. Physics definitions follow the engine (D-W1).

**W-7.3** Physics parameters, such as the gravity vector, apply to a world or to a volume within it. Physics precision, such as continuous collision detection and the substep count, can be set for each entity.

**Status:** Proposed. **Reason:** gravity as a vector lets a builder set its direction as well as its strength. Volume scope lets a machine keep its parameters when it moves to another world. Fast entities need continuous collision detection.

**W-7.4** A code block acts on another entity, a voxel volume or a world parameter only through a handle that it holds. A handle is a resource in the Component Model. The builder grants handles, within the admin's permissions (W-9.3).

**Status:** Proposed. **Reason:** resource handles are the Component Model's capability mechanism. A block can control any entity the builder grants it, such as a nearby NPC (W-6.1), and cannot reach anything else.

**W-7.5** A player or an agent can use an entity. A use arrives as an event on an `inbound` port that the entity's manifest declares for use.

**Status:** Proposed. **Reason:** a machine needs controls that an operator works deliberately. A contact sensor cannot tell a deliberate use from a collision.

## 8. The bus

**W-8.1** Blocks connect through three link kinds: busstone for simple prototyping, fibre optics for longer distances with limited mobility of the connected entities, and the wireless bus, the most powerful.

**Status:** Decided. **Source:** "busstone is good for simple prototyping, fiberoptics can be used to connect blocks over longer distances but limits the mobility of those objects.. and then wireless bus is the most powerful."

**W-8.2** All three link kinds carry the same port messages. They differ only in how a link forms and what it constrains:

| Kind | How the link forms | Constraint |
|---|---|---|
| Busstone | Busstone voxels placed between ports | Range is the length of the placed path |
| Fibre | A cable between two entities | The cable tethers the connected entities |
| Wireless | A port joins a channel | Permission; range is Open (D-W3) |

**Status:** Proposed. **Reason:** one message format lets a builder prototype in busstone and move to fibre or wireless without adjusting code.

**W-8.3** The world has one fixed simulation step for physics, the bus and block events. A message sent in step n arrives in step n + 1. Messages within a step are ordered by sender id and sequence number.

**Status:** Proposed. **Reason:** this makes block machines deterministic, which redstone-style content depends on. The step rate is Open (D-W2).

## 9. The admin world and release

**W-9.1** The admin world is a void where the admin builds and tests before anything enters a live world. In it, the admin builds creatures and imports objects.

**Status:** Proposed by the owner. **Source:** "The void can be the admins world.. testing area before its unleashed into a world"; "the admin can build creatures import objects".

**W-9.2** A world's terrain generator is a block in the admin world.

**Status:** Decided. **Source:** "a terrian generator for a world is just a block in the admins world".

**W-9.3** Code blocks exist in a live world only where the admin allows them.

**Status:** Decided. **Source:** "code blocks can exist in the world itself if the admin allows it".

**W-9.4** An assembly is the unit of release. It holds its voxels, entities, links, manifests, module hashes, asset hashes and intent records. Release copies an assembly from the admin world into a live world and records the hashes it used.

**Status:** Proposed. **Reason:** a machine moves as a whole, and hashes pin exactly what was tested.

**W-9.5** The admin controls the worlds from the void of the admin world.

**Status:** Proposed by the owner. **Source:** "Infact the void itself could be where you go to control the world".

**W-9.6** The world system has a permissions system. A right is a capability: its holder acts through a handle (W-7.4). A handle can take the form of an in-game tool, so holding the tool grants the right. The admin holds every right by default and can grant any of them. Release (W-9.4) is one such right.

**Status:** Proposed by the owner for the permissions system and for tools as permissions: "a statement that there should be a permissions system"; "sometimes a permissions can be just having a tool that can do it". The capability form is Proposed. **Reason:** it is the same mechanism as W-7.4, so players, agents and code blocks receive rights the same way.

## 10. Terrain generation

**W-10.1** A world binds one generator block. When a chunk is first needed, the world server sends the world seed and the chunk coordinates to the generator's input. The output is the chunk's voxel data. The world server stores it, and the chunk is then ordinary data.

**Status:** Proposed. **Reason:** W-2.3 and W-9.2 make the generator the only source of chunk data, and W-6 gives it ports.

**W-10.2** A generator must be deterministic. The world server records the generator's module hash with each region it generates.

**Status:** Proposed. **Reason:** an updated generator must not leave seams between old and new chunks.

**W-10.3** Generation has two stages. Stage one shapes terrain from the seed and coordinates alone. Stage two places features and can read the stage-one data of the eight neighbouring chunks.

**Status:** Proposed. **Reason:** trees, caves and structures cross chunk borders.

**W-10.4** Sandboxed in-game code can produce the data of new chunks.

**Status:** Proposed by the owner. **Source:** "is it possible for new chunks to use saneboxeed in game code. Sure why not if thats how we design it right?"

## 11. Agents in the world

**W-11.1** An agent has its own form in a world. It can take the perspective of a creature, an NPC or a boss to tune its design. Agents can also take part in games and worlds as participants.

**Status:** Decided. **Source:** "an agent already has a form ingame of its own.. but an agent can take the perspective of a creature to or npc or boss or whatever to tune its design"; "it doesnt preclude creating games and worlds where agents can also participate."

**W-11.2** A player's personal AI agent can possess and program NPCs to test in-game physics. It receives contextual knowledge selected by its task.

**Status:** Decided. **Source:** "make an interface which allows a players personal AI agent to possess and program npcs to test ingame physics, and to have access to contextual knowledge based on the task."

**W-11.3** A world is a development environment. Users and agents build and test in it.

**Status:** Decided. **Source:** "the game itself is a development environment in its own right".

**W-11.4** An agent can enter the 3D world it is building, to test its work from inside that world.

**Status:** Decided. **Source:** "it seems logical to allow the agent inside of the 3d world it is building"; confirmed: "correct".

**W-11.5** How an agent perceives and acts in a world is not chosen. The approaches under review are in `world-agent-prior-work.md`. The owner chooses after understanding them.

**Status:** Open (D-W7).

**W-11.6** What the world sends an agent is brief and targeted to the agent's task. Every word costs the agent.

**Status:** Decided, as game design. **Source:** "The biggest lesson is no verbosity, and targetted info"; "I mean as game design".

**W-11.7** Context can reach an agent both ways over ACP: the world pushes it, or the agent pulls it.

**Status:** Proposed by the owner. **Source:** "well acp affords us both."

**W-11.8** Each agent has its own browser, which renders the agent's view of the world.

**Status:** Assumption. **Source:** "agents have their own browser is what makes sense capable of rendering their view"; "I havent decided anytyhing I assumed things".

**W-11.9** The project will not have the hardware to run AI agent models itself.

**Status:** Assumption. **Source:** "running AI agents needs hardware which we wont have".

### 11.1 Reference example: Mindcraft context and commands

**Status:** reference, at the owner's direction: an example to model after for context management. Not a decision. **Source:** `kolbytn/mindcraft`, `profiles/defaults/_default.json`, `settings.js`, `src/agent/commands/`, read 2026-11-05.

**Context the agent receives each turn**, in this order:

1. Instructions: name, role, "Be very brief in your responses".
2. Memory: a summary the agent rewrites itself, at most 500 characters. It must not record stats, inventory or docs, which are delivered fresh.
3. Stats: position, game mode, health, hunger, biome, weather, time of day, current action, nearby humans and bots, modes on.
4. Inventory: item and count, one per line.
5. Command docs: each command with its parameters.
6. Examples: 2 example conversations, picked by similarity to the current one.
7. Conversation: the last 15 messages, including results of earlier commands.

**Context controls:**

| Control | Effect |
|---|---|
| Memory rewrite, 500 characters | History compresses into a fixed budget |
| `max_messages`: 15 | Old messages leave context |
| `num_examples`: 2 | Only relevant examples enter |
| `relevant_docs_count`: 5 | Code mode gets only the 5 most relevant function docs |
| Queries on demand | Nearby blocks, entities and recipes enter only when asked |
| Busy check | While an action is in progress, a short prompt decides "respond" or "ignore" for a new message |

**Commands:** the reply is brief text with at most one command, in the form `!name` or `!name(args)`.

| Kind | Examples |
|---|---|
| Queries | `!stats`, `!inventory`, `!nearbyBlocks`, `!craftable`, `!entities`, `!getCraftingPlan` |
| Actions | `!goToCoordinates`, `!followPlayer`, `!collectBlocks`, `!craftRecipe`, `!placeHere`, `!attack`, `!equip`, `!putInChest`, `!stop` |
| Vision | `!lookAtPosition`, `!lookAtPlayer`: returns a text description of the view |
| Code | `!newAction`: writes and performs code for behavior no command covers |
| Goals and modes | `!goal`, `!endGoal`, `!setMode` |

### 11.2 Reference example: Voyager context and roles

**Status:** reference, at the owner's direction: an example to model after for context management. Not a decision. **Source:** `MineDojo/Voyager`, `voyager/prompts/`, `voyager/agents/`, `voyager/voyager.py`, read 2026-11-05.

Voyager splits the work across four model roles. Each gets only the context its job needs.

| Role | Receives | Returns |
|---|---|---|
| Curriculum | Observation, completed and failed tasks | The next task |
| Action | Observation, task, context, critique, retrieved skills | Explain, Plan, one async JavaScript function |
| Critic | Observation after the attempt, task | Success true or false, and a critique |
| Skill | A function that succeeded | A description of at most 6 sentences, on one line |

**Observation the action role receives each round**, one field per line:

Code from the last round, Execution error, Chat log, Biome, Time, Nearby blocks, Nearby entities (nearest to farthest), Health, Hunger, Position, Equipment, Inventory (xx/36), Chests, Task, Context, Critique.

**Context controls:**

| Control | Effect |
|---|---|
| Skill retrieval, top 5 | Only the 5 stored skills most similar to the task enter the prompt |
| Skill descriptions | A skill is indexed by its short description, not its code |
| Last round only | Only the previous code and its error enter, not the whole history |
| Critique | The critic's verdict replaces a log of the attempt |
| Retry limit, 4 | A failing task ends after 4 attempts |
| Curriculum warm-up | An observation field enters the curriculum prompt only after a set number of completed tasks, for example `nearby_entities` after 5 and `biome` after 10 |
| Chest memory | Seen chest contents persist in a file and return as one line per chest |
| Helper rule | The action role must call skills such as `mineBlock` and `craftItem`, not the raw bot functions |

## 12. Success criteria

**W-12.1** A faithful Minecraft-like game is built on the void as content only: a terrain generator, redstone from WASM blocks, tools and crafting. No adjustment to the core is needed.

**Status:** Decided. **Source:** "if we can faithfully replicate a terrain generator, restone using wasm blocks, tools and crafting, where the server itself is the void and the simulacrum can be built ontop in a safe way that doesnt require changing the system core.. thats a good success".

**W-12.2** A builder can make a machine from the host interface alone: an imported 3D object attached to a code block by a joint, moved by the code block through its ports, in a world or volume with adjusted physics.

**Status:** Decided. **Source:** "its to build a system that can".

**W-12.3** A void world with no edits stores zero chunk bytes.

**Status:** Proposed. Follows from W-3.3.

## 13. Open decisions

| ID | Decision | Recommendation | Blocks |
|---|---|---|---|
| D-W1 | Physics engine: Avian, Rapier or Box3D (world-ideas) | Avian, because it keeps physics state as Bevy components. Confirm by a fixture with a joint motor, continuous collision detection and a repeat-determinism check. | W-4.4, W-7.2, W-7.3 |
| D-W2 | Simulation step rate | 60 steps a second, with per-entity substeps (W-7.3). 20 a second, as in Minecraft, is too slow for fast machines. | W-8.3 |
| D-W3 | Wireless range and cost | Range set per world by the admin; channel use needs permission. | W-8.2 |
| D-W4 | Where code takes effect for latency-sensitive play | The server is the authority. A client predicts only the entity its player or agent controls. | W-11.2, W-12.2 |
| D-W6 | Limit values for W-6.3 | Measure first; set values from the Minecraft-like content of W-12.1. | W-6.3 |
| D-W7 | How an agent perceives and acts in a world | None yet. The owner is reviewing the approaches in `world-agent-prior-work.md`. A new tool needs an owner decision (`DECISIONS.md`). | W-11.2, W-11.5 |
| D-W9 | The client and renderer | A Three.js client over a headless Bevy server, with one Rust crate compiled to WASM in the browser for protocol decoding, chunk meshing and prediction. | W-1.3, D-W4 |
| D-W10 | How an agent's task context is selected from the world graph and delivered (W-5.6) | None yet. The functional map composes layers on each address and selects them with a resolver (`TOPOGEE.md` section 2); that is one model to compare against. | W-5.6, W-11.2 |
