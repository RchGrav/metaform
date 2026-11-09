# World System Specification

**State:** draft, 2026-11-05. Written by Claude (Opus 5.5) at the founder's direction. The founder has not reviewed it.

This document specifies the world system: the world server, its worlds, and how people and agents build inside them. Topogee is not a game, though it has the bones of one: it is a world where agents and people collaborate and build anything, including the world itself (`DECISIONS.md`, "Naming: Topogee and Metaform"). It is separate from `metaform/SPEC.md`. The specification is the system that can build any in-game machine. It does not specify any machine.

## How to read this document

Every requirement carries one status:

- **Decided:** the founder stated it. The source gives the founder's words.
- **Proposed by the founder:** the founder suggested it ("could", "can") and has not confirmed it as final.
- **Proposed:** an agent proposed it, with its reason. The founder has not confirmed it.
- **Assumption:** the founder stated it while exploring and has not decided it.
- **Open:** the founder must decide it. Section 13 lists each one with a recommendation.

Founder sources are from the session of 2026-11-04 and 2026-11-05 unless another source is named. `world-ideas` means `docs/world-ideas.md`. "The brief" means the founder topic brief in `docs/roundtables/session-20261104-24c67015/review-evidence.md`.

This document contains no analogies. Words such as "must" apply to the implementation.

## Built so far (2026-11-07)

A working void world, live-tested. In `topogee/` (see `topogee/README.md`):

- **L1 edge:** WebTransport (no WebSocket fallback), login and registration on a SQLite accounts store with Argon2id and one owner, agent accounts issued in the world by a logged-in person.
- **L2 data:** a headless Bevy ECS on a 60 Hz fixed step; voxels in Anvil-style region files (`world-store`: palette, culling, region grouping; a void world stores zero region bytes, W-12.3); the world graph in LadybugDB (`world-graph`: blocks, ports, links, modules by hash, block state), each store with one owner and one writer.
- **L3 communication:** the `world` chat channel.
- **L6 and L7:** the void (W-2.1 to W-2.3); code blocks as WebAssembly components on `topogee:host@0.2.0`, whose bus messages carry a kind and data bytes (W-6.5) (W-6.1, W-7.1), events only (W-6.2), fuel and memory limits with fault isolation (W-6.3), busstone links delivering in the next step (W-8.3). Proof-of-concept machines: a switch and lamp, a clock that blinks a lamp, a greeter and sign; block state survives a restart.
- **L8 and agents:** one MCP tool, `world` (look, move, say, chat, use), through which an agent from any harness logs in with its token and acts; tested live with an agent using the switch, watching the clock and being greeted by name.
- **Client:** Three.js with the founder's agent figures. Verified 2026-11-07 in Chrome 156 (Windows, headless, driven over the DevTools protocol): register, chat, walk, click the switch to light lamp A, and lamp B blinking on the clock (`topogee/docs/screenshots/`).

## 0. Layers

Topogee is built in layers, from the outside in. Each layer builds on the layers listed before it.

**Status:** Proposed by the founder: "we need to approach topogee in layers, outside layer will be hub, auth, networking etc, next will be the ECS and binary highspeed storage and GraphDB layer *ladybug, user channels, chat messaging, async, core features, engine and physics, void world (voxel world w/ other custom engines and objects , mechanics, dev tools in that world.. You are the dev but this is whatg I see in my head." (2026-11-07). The mapping and gaps below are the design reviewer's.

| Layer | Holds | Specified so far | Gaps |
|---|---|---|---|
| L1 Edge | The hub, authentication, networking | The hub idea and ACME with dynamic DNS (`docs/world-ideas.md`, "Hosting"); WebTransport with no WebSocket fallback (`DECISIONS.md`) | Authentication and identity: nothing specified |
| L2 Data | The ECS, high-speed binary storage, the graph database | Bevy (W-1.3); the chassis is Rust, Bevy and event driven (`DECISIONS.md`, "The chassis"); region files (W-3.2, W-3.3); one LadybugDB database per world (W-3.5); tested limits (`docs/world-ideas.md`, "Tested") | How ECS state reaches binary storage and the graph, and when |
| L3 Communication | User channels, chat and messaging, asynchronous work | Agents enter a channel and keep one shared state (draft requirements R15); the lightweight mailbox (`DECISIONS.md`) | Channels, chat and messaging: nothing specified |
| L4 Core features | Not yet defined | | What belongs here (D-W16) |
| L5 Engine | The engine and physics | Physics capabilities (W-4.4); the engine choice (D-W1); the step rate (D-W2) | Where the WASM runtime sits (D-W17) |
| L6 World | The void world: voxels, with other custom engines and objects | The void (section 2), storage (section 3), shapes and fluids (3.1), entities (section 4), the world graph (section 5) | |
| L7 Mechanics | How things behave in a world | Code blocks (section 6), the bus (section 8), content on a fixed core (W-2.5), the Minecraft benchmark (W-12.1a) | |
| L8 Dev tools | Development tools inside the world | Agents in the world (section 11); Metaform instances in the world (W-1.1, `metaform/SPEC.md` R-4.14, R-4.15) | Which tools, and how agents and people use them in a world |

**W-0.1** Identity belongs to L1 and is used by every layer: channels (L3), permissions and land claims (L6, L7), private Metaform maps (L8), and the launcher's process identities. It is the most foundational gap, because each of those waits on it.

**Status:** Proposed. **Reason:** `metaform/SPEC.md` R-4.15 and R-8.2, the launcher design and section 9 (admin rights) all depend on knowing who is acting, and nothing yet says how that is established.

**W-0.2** "Core" has two meanings in this document: the world core of W-2.5 (the void, the three content kinds, the three systems, the bus and the host interface), which spans L5 to L7, and the core features of L4. One of them needs another name.

**Status:** Proposed. **Reason:** TASTE gives each term one meaning.

## 1. Scope and separation

**W-1.1** The project's own functional map is an engineering tool for building the system. It has no role inside a world. The world system never reads or writes it, and players never extend it. Metaform itself is a tool used inside the game: agents and players run their own Metaform instances to design features, worlds and anything else that needs a specification (`metaform/SPEC.md` R-4.14).

**Status:** Decided. **Source:** "The functional map itself can be used to develop the system, it doesnt work as a ingame tool."; "we are not seeking to have players expand our internal specification and blueprint we have in the form of our functional map we use as an engineering tool.. that would be the wrong approach".

**Narrowed 2026-11-07:** the founder: "metaform will be used in game to design features worlds or anything that requires a specification". The first part of W-1.1 stands for the project's own map; the last sentence is new.

**W-1.1a** An agent planning anything in the game can create its own map to define the functionality of what it is building, and refer from that map to the WASM objects that realize it. Agents create maps to collaborate on specifications with other agents. The project's own map (W-1.1) cannot be addressed from inside the game. A map in the game uses the same address space as a map outside it, with the same references and internal references; it is a different map, not the external one. How this plays out in game mechanics, for example storage blocks, is not decided: the game has no rules yet.

**Status:** Decided, except the mechanics. **Source:** the founder, 2026-11-07: "Any agent planning anything in the game can create their own map to define the functionality of what they are building and then reference the wasm object. how that plays out in game mechanics we might end up having storage blocks.. I dont know yet.. we dont have rules its primodial at this point"; "you cant address the external map from inside of the game but agents can create their own to collab abd build specifications with other agents."; "address space is the same ingame as outside.. refs and internal refs, its not the same external map though". Private maps already exist in Metaform (`metaform mcp --map`, `metaform/SPEC.md` R-4.15).

**W-1.2** The link record between functional addresses and world entities (roundtable P4, P7 and L-33) does not apply to in-game entities. The world server's own source code takes an intake like any other project.

**Status:** Proposed. **Reason:** W-1.1 removes the purpose of that link. The second sentence follows from "can be used to develop the system".

**W-1.3** The world server is written in Rust, uses Bevy and stores world data in LadybugDB. The client is a thin Three.js client. One private install serves a group of friends.

**Status:** Decided for the server and the install. The Three.js client is Proposed by the founder: "I was proposing a threejs thin client as bevys renderer". The client options are Open (D-W9). **Source:** the brief: "World server (Rust, LadybugDB + Bevy) · UI (Three.js)"; "One private install shared by a group of friends". world-ideas: "Three.js as a thin client".

**W-1.4** The world system needs its own MCP server, built custom and inspired by metaform. The Node functional map server is for developing the system; it cannot serve the system itself, because agents must be able to blueprint their features, and the functional map's namespace setup does not support that.

**Status:** Decided. **Source:** "our map server isnt going to be able to run in node for the game.. the issue is that we need to allow agents the ability to blueprint their features and the base functional map and its namespace setup wont work for that so our node based mcp server is good foe developing the system, but wont work for the systems mcp server we came to the realization that we will need to make something custom that is inspired by metaform" (2026-11-05). What a feature blueprint holds and how agents write it are not specified yet; W-5.3 and W-5.5 describe the closest parts so far. **Reconsidered by the founder on 2026-11-06, not yet settled:** "I might have been wrong saying we need to make one specifically for topogee.., what I think we do need to allow if for agents to build their own metaform map to describe whatever it is they intend to build and give them ownership of their own metaform". See `metaform/SPEC.md` section 11, collaboration.

## 2. The void and the world

**W-2.1** A world starts as the void: voxel-addressable space with an invisible floor, no materials, no items and no rules.

**Status:** Decided. **Source:** "there is a floor you cant see but you are standing on something"; "my default there is no materials, there is no rules.. there is the void"; "the void is voxel based (addressible) but no items are defined".

**W-2.2** A world has the vertical limits of Minecraft Java Edition 1.18 and later: build height from y = −64 to y = 319, 384 blocks. The invisible floor is at y = −64, the bedrock level.

**Status:** Decided for "the same limits as MC for height and bedrock". The version and the floor position are Proposed. **Reason:** 1.18 is the current Minecraft height range. The founder placed the floor where bedrock is.

**W-2.2a** In a void, the spawn point is x = 0, z = 0, standing on the invisible floor: the occupied cell is y = −64. A world's spawn point moves only when the admin sets it, or when the world's generator reports one through an output port (W-10.1).

**Status:** Proposed by the founder for the void spawn: "in the void a system admin spawns in the void at x=0 z=0 at y-64 right?" The rule for moving the spawn is Proposed. **Reason:** Minecraft searches near the origin for a surface. A void has no surface, so the origin on the floor is the only defined point. A generator is content, so it reports a spawn and does not set one in the core.

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

**Status:** Decided. **Source:** the founder: "DoD is we undo wrong inference about data storage, we will be using the core architectural storage concepts from anvil, ie • Region-Chunk Grouping: Grouping small chunks (e.g., 16³ or 32³) into larger region files or database partitions to prevent OS filesystem bottlenecks from tens of thousands of tiny files. • Palette Compression: Mapping unique block states per chunk to small bit-packed integer indices rather than storing full block IDs or strings for every voxel. • Empty-Section Culling: Omitting uniform or air-only vertical sections from disk serialization entirely. combined with ladybugdb. dod working void world with a few proof of concept uses of wasm bus in it." (2026-11-07, relayed by Jorge from session topogee-c5). The sizes follow Minecraft's, which W-2.2 already follows, so Minecraft-like content (W-12.1) maps one to one. The vertical range is W-2.2's: section 0 starts at y = -64.

**W-3.3** A section stores a palette of distinct cell values and a bit-packed index for each voxel. An empty section stores nothing. A region file holds an offset table and one compressed record per chunk.

**Status:** Decided. **Source:** the founder's storage goal (W-3.2). Reading of "uniform ... sections" (Jorge and Xander, 2026-11-07): an air section stores nothing; a section of one non-air material stores one palette value and no index bits, so its material is kept. Built in `topogee/crates/world-store`.

**W-3.4** A voxel cell holds a material reference or nothing. Each voxel subdivides into an 8 × 8 × 8 grid that shape points snap to. A code block (W-6.1) is an entity. Its voxel coordinate and its code module instance are components of that entity.

**Status:** Proposed for the cell fields and the code block. The 8 × 8 × 8 grid is a founder idea in world-ideas ("Every block is an 8×8×8 grid that points snap to").

**W-3.5** Each world stores entities, ports, links, manifests and intent records in its own LadybugDB database. Region files hold voxel data. Code modules and imported assets are stored once, keyed by the hash of their contents.

**Status:** Decided for voxels in region files and the world graph in LadybugDB ("combined with ladybugdb", W-3.2). Voxels never become Ladybug nodes. Each store has one named owner and one write queue (`DECISIONS.md`: "write queues on everything"). Content keys are Proposed (an agent suggestion in world-ideas).

**W-3.6** Particles are simulated and never saved.

**Status:** Proposed. **Reason:** particle counts are high and their state is short-lived. A code module that needs a lasting effect writes voxels or spawns entities.

**W-3.7** The world server keeps a chunk loaded while something holds a load ticket on it. By default, only players hold tickets, within the simulation distance. The admin can hold tickets and can grant the ticket handle to code blocks, links or agents (W-7.4).

**Status:** Proposed. **Reason:** load tickets are how Minecraft keeps chunks loaded, and `/forceload` is an admin privilege on them, not a base capability. A grantable handle lets a world add ticket sources as content, with no change to the core.

### 3.1 Shapes, breakage and fluids

These items come from the founder's brainstorm of 2026-11-02 (`docs/world-ideas.md`). Under W-2.5, carving tools, materials, breakage rules and water are content. The core supplies only the operations that content needs. Roundtable 7 left fluids and fracture out of scope; the founder's brainstorm makes them central, so they are specified here.

**W-3.8** A voxel cell can hold a shape: a closed surface whose points snap to the cell's 8 × 8 × 8 grid (W-3.4). The outer surface of the cell is part of the shape. A shape is stored once, keyed by the hash of its contents, and cells refer to it.

**Status:** Assumption for the shape: "A shape is a manifold object that uses the grid as snap-to points. The outer surface is part of the manifold shape." Proposed for storage. **Refined 2026-11-07** by the founder's block-damage statement (W-3.18 to W-3.22): a damaged block is stored as cells and the local states of its surfaces, and its mesh is generated from them; a stored shape is that state, still kept once by hash. **Reason:** identical shapes are common, so one stored copy keeps region files small (agent suggestion in world-ideas).

**W-3.9** The core accepts a shape only if every edge is shared by exactly two triangles, no triangles cross, and every point is on the grid and inside the cell. The same check applies whoever made the shape: a tool, an agent or an import.

**Status:** Superseded by W-3.20 (founder, 2026-11-07, asked whether this triangle check still applies after the block-damage statement): "matter is programmable ... but I think my new approach is better". A damaged block's surface is generated from cell, edge and corner states (W-3.20, W-3.21), so validity comes from those states, not from a check on triangles. Earlier reason, kept for the record: one check keeps every shape valid for physics and meshing.

**W-3.10** The host interface has one cut operation. It splits a shaped cell along a path of grid points into parts and reports which parts touch a neighbouring cell. Content decides which parts stay. The default content rule is the founder's: the part attached to another block stays, then the smallest unattached part is removed. A cut can continue into the next cell; it must exit on a face that is not connected, and it cannot backtrack through or over a point.

**Status:** Assumption for the rule and the continuation: "The side attached to another block wins. After that, the smallest part of the unattached sides is removed." Proposed for the split between core and content. **Reason:** W-2.5 keeps rules out of the core. One operation serves carving and collision deformation, which the founder said "works the same way as carving".

**W-3.11** The host interface can turn a part of a cell into an entity with a physics body, and turn an entity back into a shaped cell. A sheared or detached part is an ordinary entity. An entity pushed back into place becomes a shaped cell again.

**Status:** Assumption: "A sheared block that is attached is no longer a voxel"; "Detached objects are ordinary 3D objects in the world. If one is pushed back into place, it becomes a shaped voxel again." Proposed for the two operations. **Reason:** content needs both directions to build breakage and repair.

**W-3.12** Whether a detached entity comes to rest aligned with the grid is a setting of the content that made it, not a rule of the core.

**Status:** Assumption: "I wonder if we could let things act like physics but force them to come to a stop where they align with that grid". Proposed as content. **Reason:** some content wants loose rubble and some wants rubble that rebuilds into voxels.

**W-3.13** Strength is material data. A material's content defines its stress values from the material and the wall thickness, and decides when a cell shears. The core supplies the contact forces and impulses (W-7.2, sensors) that the decision needs.

**Status:** Assumption: "Materials and wall thickness give stress values. Something might need more force to go deep. Brick might shear." Proposed as content. **Reason:** W-2.5 makes every material content.

**W-3.14** A cell can hold a small value that belongs to its material's code, such as a water level in eighths. The core stores the value with the cell and does not interpret it.

**Status:** Proposed. **Reason:** the founder's water has levels ("A water block has 7 different values"; "Water depth steps are 12.5 cm", one eighth of a block). One generic value serves water and any other material with stages, so the core holds no water rule. The size of the value is Open (D-W12).

**W-3.15** Water is content: a material whose code moves level between cells. It drains, flows down carved paths, spreads when it has nowhere to go, and soaks into absorbent materials such as dirt.

**Status:** Assumption: "Water can flow down a chiseled path. If it has nowhere to go, it spreads out, and it absorbs into dirt." **Reason** for content: W-2.5 and W-12.1 (water must be buildable on the void).

**W-3.16** Each face of a shaped cell records which of its 8 × 8 parts are open, so content can tell whether water passes between two cells.

**Status:** Proposed. **Reason:** water needs to know where carving has opened a path. The record is derived from the shape and computed once per shape (agent suggestion in world-ideas).

**W-3.17** The authoritative state of water is its cell levels. Particle effects, such as spray and crest particles, only show it and are never saved (W-3.6).

**Status:** Proposed. **Reason:** levels in cells are deterministic and cost little to store. The founder shared particle methods (SPH, PBF, and a hybrid with flat wave math and particles at the crests); D-W13 decides which one draws water.

### 3.2 Block damage

These requirements come from the founder's block-damage statement, `docs/owner-statements-2026-11-07-block-damage.md`: "exactly what I conveyed" (2026-11-07). Block damage is one application of the WASM sandbox and the event data bus, not their purpose.

**W-3.18** A block begins as a cube and can be changed into a manifold solid. Chiselling removes material, slicing makes a flat face, and a projectile impact can knock off chips. The resulting shape lasts as part of the block's state. Two kinds of change are central: shearing, a planar cut that leaves a flat surface, defined by points selected on the outer surface or by a directed slicing action; and chipping, which removes a local piece and changes the adjacent edges into angled fracture surfaces rather than a square recess.

**Status:** Decided. **Source:** `docs/owner-statements-2026-11-07-block-damage.md`, "Damage behavior".

**W-3.19** How a material shears or chips is programmable. The material's WASM program receives the interaction, such as an impact with position, direction and energy, decides what material is removed and how the adjacent surfaces change, and emits the resulting events on the bus. The geometry representation defines what shapes can exist; material programs define how interactions produce them.

**Status:** Decided. **Source:** `docs/owner-statements-2026-11-07-block-damage.md`, "Material-controlled response" and "Integration with the event data bus". The bus already carries structured data (`topogee:host` 0.2.0: a message is a kind and its bytes).

**W-3.20** The set of possible shapes is bounded without a catalogue of every damaged block. Each block is subdivided into smaller cells (the 8 × 8 × 8 of W-3.4). Removing a cell also changes the exposed geometry of its neighbours, producing angled faces and altered edges. A finite set of local cell, edge and corner states combines into the whole shape. Shared boundaries, inside a block and between blocks, fit together so the surface stays continuous and manifold.

**Status:** Decided for the direction. **Source:** `docs/owner-statements-2026-11-07-block-damage.md`, "Limiting the possible geometry". The exact representation, including how sheared surfaces fit into it, is Open (D-W18). Proposed for the shared boundaries: each block owns the corners 0 to 7 along each axis, and its far faces use the neighbour's corner 0, so every corner has one owner (founder, 2026-11-07: "if you off set that only one side owns the edge").

**W-3.21** A damaged block keeps enough state to rebuild its shape. The visible mesh is generated from that state, not stored.

**Status:** Decided. **Source:** `docs/owner-statements-2026-11-07-block-damage.md`, "Persistent state": "store the remaining cells and the local geometric states needed to describe their cut or fractured surfaces, then generate the visible mesh from that representation" (a candidate approach; the representation is D-W18).

**W-3.22** Damage takes part in the event data bus. An interaction delivers structured information to a block, triggers its material behaviour, changes its geometric state, and produces further events, so surrounding blocks and other systems can respond to the details of an impact or a material change.

**Status:** Decided. **Source:** `docs/owner-statements-2026-11-07-block-damage.md`, "Integration with the event data bus": "The bus carries event data rather than only a power level."

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

**Status:** Proposed. **Reason:** the founder requires that content not harm the core (W-2.5). Wasmtime fuel metering gives a deterministic instruction budget in Rust. The limit values are Open (D-W6).

**W-6.4** Code that an agent generates is not a safety risk in this design.

**Status:** Decided. **Source:** "unlike their approach generated code isnt a safety risk in our design". **Reason**, Proposed: generated code runs only as a WASM module, under the limits of W-6.3, and reaches the world only through the host interface (W-7.1).

**W-6.5** A block is a WASM program's physical existence in the world. It holds code, and it can be as simple or as complex as its builder wants. The world graph connects blocks, and what connects them is more than a simple redstone connection: a WASM bus, an event-driven, asynchronous, tick-based data bus.

**Status:** Decided. **Source:** the founder, 2026-11-07: "wasm uses a block as its physical existance in the world.. and this is wasm, this replaces restone, that means a block can be as complex or simple as you want, it holds code.. the graphdb system is what connects them together, and what connects them is more than justy a simple redstone connections, it a wasm bus, IE. and event driven async tick based data bus".

**W-6.6** A block can stand for any kind of data into or out of the system: anything that can be connected with WASM. For example, a computer brought into the world, with its terminal mapped onto a screen in the world through a data connection.

**Status:** Decided. **Source:** the founder, 2026-11-07: "a block can act as a metaphor or any kind of data in and out of the system, data, really anything you can connect with WASM, you want to bring in a computer and map a terminal ojn the screen do it with a data connection."

**W-6.7** A block is limited only by what it is allowed to do. Blocks are the basis of everything that can be built in the system. A block's reach comes from the rights granted to it (W-7.4, W-9.6), not from a fixed ceiling: its budgets (W-6.3) and any connection outside the world are granted per block.

**Status:** Decided. **Source:** the founder, 2026-11-07: "blocks are only limited by what they are allowed to do they are the whole basis of the whole constructability of the system, these can be kept in an admin area like the white void in the matrix.. this is where you can create an admin like area , all of your controls and settings..   wherre you can map a input to control objects.. you essentially ask an AI to build you code and it lives in a block, that is the physical sanboxed manifestation of whatever you want it to be." The per-block grant of budgets and outside connections is Proposed, as the reading of "only limited by what they are allowed to do".

**W-6.8** A person asks an AI to build code, and the code lives in a block: the physical, sandboxed manifestation of whatever the person wants it to be.

**Status:** Decided. **Source:** as W-6.7.

## 7. The host interface

**W-7.1** The host interface is the only way code reaches the world. It is a set of WIT interfaces in semantically versioned packages. A code module is a WebAssembly component. It imports the host interfaces it uses, at the versions it targets, and the world server provides only those imports.

**Status:** Proposed. **Reason:** the WebAssembly Component Model is the standard for typed, versioned host interfaces, and Wasmtime implements it. A component reaches only what it imports, which is the WASI capability model. W-2.5 makes this interface the boundary of the core.

**W-7.1a** Besides the host interface, code is given an empty WASI: what a language's standard library needs to run (memory allocation, formatting, panics), with output discarded and no files, no network, no environment variables and no arguments. It reaches nothing; the host interface remains the only way code reaches the world. It applies to code blocks, block-type programs and generators.

**Status:** Decided. **Source:** the founder, 2026-11-07, choosing "Yes, empty WASI" when asked: "Code inside blocks can't allocate memory today: any Rust that builds a String or a Vec drags in WASI, which the sandbox refuses. That makes AI-written block code very awkward ... I propose linking an empty WASI ... Blocks still only touch the world through the host interface." **Reason:** code an AI writes for a block (W-6.8) is ordinary code, and ordinary code allocates.

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

**Status:** Proposed by the founder. **Source:** "The void can be the admins world.. testing area before its unleashed into a world"; "the admin can build creatures import objects".

**W-9.2** A world's terrain generator is a block in the admin world.

**Status:** Decided. **Source:** "a terrian generator for a world is just a block in the admins world".

**W-9.3** Code blocks exist in a live world only where the admin allows them.

**Status:** Decided. **Source:** "code blocks can exist in the world itself if the admin allows it".

**W-9.4** An assembly is the unit of release. It holds its voxels, entities, links, manifests, module hashes, asset hashes and intent records. Release copies an assembly from the admin world into a live world and records the hashes it used.

**Status:** Proposed. **Reason:** a machine moves as a whole, and hashes pin exactly what was tested.

**W-9.5** The admin controls the worlds from the void of the admin world.

**Status:** Proposed by the founder. **Source:** "Infact the void itself could be where you go to control the world".

**W-9.7** The admin area is a void like the white loading room in The Matrix. It holds all of the admin's controls and settings as blocks, and there the admin maps an input to control objects.

**Status:** Decided. **Source:** as W-6.7. It adds controls, settings and input mapping to the admin world of W-9.1 and W-9.5.

**W-9.8** Security comes down to who has the permission to create a feature in the game. Anyone can interact with features once they exist.

**Status:** Decided. **Source:** the founder, 2026-11-07, after "you should be thinking about bus security": "I think it comes down to who has the permision to create certain features in game, anyone can interact with them". The bus rules that follow are in `docs/designs/world-proof-path.md`, "Bus security".

**W-9.9** The base of the permissions system: the person running the server names the admin when starting it. The admin holds every right and grants or revokes rights for accounts. A person can pass rights they hold to their own agents, never more than they hold. Creating a code block or a link needs a right (W-9.8); a link needs rights on both blocks it joins.

**Status:** Decided. **Source:** the founder, 2026-11-07, choosing "Yes, build that" for the proposal: "the person running the server names the admin when starting it (--admin <name>). The admin holds every right and grants or revokes rights for accounts with chat commands (/grant, /revoke). A person can pass rights they hold to their own agents, never more than they hold. A link needs rights on both blocks." The command names are the proposal's; rights as in-game tools (W-9.6) come later.

**W-9.6** The world system has a permissions system. A right is a capability: its holder acts through a handle (W-7.4). A handle can take the form of an in-game tool, so holding the tool grants the right. The admin holds every right by default and can grant any of them. Release (W-9.4) is one such right.

**Status:** Proposed by the founder for the permissions system and for tools as permissions: "a statement that there should be a permissions system"; "sometimes a permissions can be just having a tool that can do it". The capability form is Proposed. **Reason:** it is the same mechanism as W-7.4, so players, agents and code blocks receive rights the same way.

## 10. Terrain generation

**W-10.1** A world binds one generator block. When a chunk is first needed, the world server sends the world seed and the chunk coordinates to the generator's input. The output is the chunk's voxel data. The world server stores it, and the chunk is then ordinary data.

**Status:** Proposed. **Reason:** W-2.3 and W-9.2 make the generator the only source of chunk data, and W-6 gives it ports.

**W-10.2** A generator must be deterministic. The world server records the generator's module hash with each region it generates.

**Status:** Proposed. **Reason:** an updated generator must not leave seams between old and new chunks.

**W-10.3** Generation has two stages. Stage one shapes terrain from the seed and coordinates alone. Stage two places features and can read the stage-one data of the eight neighbouring chunks.

**Status:** Proposed. **Reason:** trees, caves and structures cross chunk borders.

**W-10.4** Sandboxed in-game code can produce the data of new chunks.

**Status:** Proposed by the founder. **Source:** "is it possible for new chunks to use saneboxeed in game code. Sure why not if thats how we design it right?"

## 11. Agents in the world

**W-11.1** An agent has its own form in a world. It can take the perspective of a creature, an NPC or a boss to tune its design. Agents can also take part in games and worlds as participants.

**Status:** Decided. **Source:** "an agent already has a form ingame of its own.. but an agent can take the perspective of a creature to or npc or boss or whatever to tune its design"; "it doesnt preclude creating games and worlds where agents can also participate."

**W-11.2** A player's personal AI agent can possess and program NPCs to test in-game physics. It receives contextual knowledge selected by its task.

**Status:** Decided. **Source:** "make an interface which allows a players personal AI agent to possess and program npcs to test ingame physics, and to have access to contextual knowledge based on the task."

**W-11.3** A world is a development environment. Users and agents build and test in it.

**Status:** Decided. **Source:** "the game itself is a development environment in its own right".

**W-11.4** An agent can enter the 3D world it is building, to test its work from inside that world.

**Status:** Decided. **Source:** "it seems logical to allow the agent inside of the 3d world it is building"; confirmed: "correct".

**W-11.5** How an agent perceives and acts in a world is not chosen. The approaches under review are in `world-agent-prior-work.md`. The founder chooses after understanding them.

**Status:** Open (D-W7).

**W-11.6** What the world sends an agent is brief and targeted to the agent's task. Every word costs the agent.

**Status:** Decided, as game design. **Source:** "The biggest lesson is no verbosity, and targetted info"; "I mean as game design".

**W-11.7** Context can reach an agent both ways over ACP: the world pushes it, or the agent pulls it.

**Status:** Proposed by the founder. **Source:** "well acp affords us both."

**W-11.8** Each agent has its own browser, which renders the agent's view of the world.

**Status:** Assumption. **Source:** "agents have their own browser is what makes sense capable of rendering their view"; "I havent decided anytyhing I assumed things".

**W-11.10** Agents in the game speak normal English. The project's writing rules (TASTE, and the field rules of the documentation set, such as no words ending in -ing in `why` and `how`) are for technical writing, such as the project's own map and its documents, and have nothing to do with what players do.

**Status:** Decided. **Source:** the founder, 2026-11-07, answering whether Metaform should refuse -ing words in `why` and `how`: "thats for technical writing which has nothing to do with what players do, but ideally agents in the game speak normal english". So any enforcement of those rules belongs to technical maps, not to maps or chat in the game.

**W-11.9** The project will not have the hardware to run AI agent models itself.

**Status:** Assumption. **Source:** "running AI agents needs hardware which we wont have".

### 11.1 Reference example: Mindcraft context and commands

**Status:** reference, at the founder's direction: an example to model after for context management. Not a decision. **Source:** `kolbytn/mindcraft`, `profiles/defaults/_default.json`, `settings.js`, `src/agent/commands/`, read 2026-11-05.

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

**Status:** reference, at the founder's direction: an example to model after for context management. Not a decision. **Source:** `MineDojo/Voyager`, `voyager/prompts/`, `voyager/agents/`, `voyager/voyager.py`, read 2026-11-05.

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

**W-12.1a** The bus replaces redstone in the core. Redstone is emulated as content on the bus. A milestone is a proof of concept that implements Minecraft's mechanics and emulates the game, shown with a community texture pack. The proof of concept is a technical benchmark. The project never claims to be a Minecraft clone of any kind.

**Status:** Decided. **Source:** "instead of redstone we use a bus, but we could emulate redstone.. infact being able to do so with the community texture pack should be a milestone.. the ability to implement the mechanics of minecraft and emulate the game as a PoC should be a goal we should see without ever claiming to be a minecraft clone of any kind.. because we are far from it, but using it as a technical watermark is a good test." (2026-11-07). Which texture pack is Open (D-W11).

**W-12.2** A builder can make a machine from the host interface alone: an imported 3D object attached to a code block by a joint, moved by the code block through its ports, in a world or volume with adjusted physics.

**Status:** Decided. **Source:** "its to build a system that can".

**W-12.3** A void world with no edits stores zero chunk bytes.

**Status:** Proposed. Follows from W-3.3.

## 13. Open decisions

| ID | Decision | Recommendation | Blocks |
|---|---|---|---|
| D-W1 | Physics engine: Avian, Rapier or Box3D (world-ideas) | **Decided by the founder, 2026-11-08: Avian** ("Avian (Recommended)", asked "The physics engine (D-W1) is the last thing holding back creatures, dropped items and minecarts driven by code. Which one?"). avian3d 0.8.0 targets Bevy 0.20 and builds headless with its default features off (Jorge, 2026-11-08). | W-4.4, W-7.3 |
| D-W2 | Simulation step rate *(default taken 2026-11-07 for M1: 60 steps a second; `docs/designs/world-protocol.md`)* | 60 steps a second, with per-entity substeps (W-7.3). 20 a second, as in Minecraft, is too slow for fast machines. Emulated redstone (W-12.1a) can still keep Minecraft's 20-a-second timing, because 60 is a multiple of 20: the content advances once every 3 steps. | W-8.3, W-12.1a |
| D-W3 | Wireless range and cost | Range set per world by the admin; channel use needs permission. | W-8.2 |
| D-W4 | Where code takes effect for latency-sensitive play | The server is the authority. A client predicts only the entity its player or agent controls. | W-11.2, W-12.2 |
| D-W6 | Limit values for W-6.3 | Measure first; set values from the Minecraft-like content of W-12.1. | W-6.3 |
| D-W7 | How an agent perceives and acts in a world | None yet. The founder is reviewing the approaches in `world-agent-prior-work.md`. A new tool needs a founder decision (`DECISIONS.md`). | W-11.2, W-11.5 |
| D-W9 | The client and renderer | A Three.js client over a headless Bevy server, with one Rust crate compiled to WASM in the browser for protocol decoding, chunk meshing and prediction. | W-1.3, D-W4 |
| D-W10 | How an agent's task context is selected from the world graph and delivered (W-5.6) | None yet. The functional map composes layers on each address and selects them with a resolver (`TOPOGEE.md` section 2); that is one model to compare against. | W-5.6, W-11.2 |
| D-W11 | Which community texture pack the W-12.1a milestone uses | A pack whose license allows use and redistribution in a private install, with no Mojang assets in it. Check the license before the milestone starts. | W-12.1a |
| D-W12 | The size of the per-cell material value (W-3.14) | 4 bits: enough for water levels 0 to 8 and other staged materials, and cheap in a palette. | W-3.14, W-3.15 |
| D-W13 | How water is drawn (W-3.17): SPH, PBF, or flat wave math with particles at the crests | The hybrid, because cell levels already give the flat surface, and crest particles add motion only where water moves fast. | W-3.17 |
| D-W14 | If a cut pinches a shape into two parts that still touch, is it one cell or two? (world-ideas) | Two parts in one cell while both touch neighbours; a part that touches nothing becomes an entity (W-3.11). | W-3.10 |
| D-W15 | Does an impact stop at the cell it hits, or carry into the cells behind? Do chips that fade away destroy matter? (world-ideas) | Content decides both. The core reports the impulse at each contact; matter counting is content too. | W-3.11, W-3.13 |
| D-W16 | What layer L4, core features, holds | Ask the founder; candidates are accounts and inventories, permissions and land claims, and world administration (section 9). | L4 |
| D-W17 | Which layer the WASM runtime and the bus sit in | The runtime (Wasmtime and the host interface, section 7) in L5, beside physics, because it runs on the engine's step; the bus (section 8) in L7, because it carries mechanics. | L5, L7 |
| D-W18 | How a damaged block is represented so that both angled chips and flat shears at any angle fit (W-3.20, W-3.21) | A small value at each corner of the 8 × 8 × 8 cells, saying where the surface crosses, with the mesh generated by a fixed local table (the marching-cubes family). Plain present-or-absent cells give chips but turn a slanted shear into steps; corner values give both from one representation. About 256 bytes per damaged block at 4 bits per owned corner, stored once by hash. | W-3.20, W-3.21 |
| D-W19 | The first form of bodies driven by code (W-6.1, proof-path item 6) | A code block owns up to 16 bodies, steers them on its timer and reads the cells around it to find a way; a body carrying its own code can come later as another form. | W-6.1, W-7.4 |
| D-W20 | Whether making bodies needs its own right | No: the block that makes them was placed under `place_code`, its limits cap the bodies, and the admin can switch it off. | W-9.8, W-9.9 |
