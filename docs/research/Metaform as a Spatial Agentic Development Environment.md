# Metaform as a Spatial Agentic Development Environment

## Executive conclusion

The strongest interpretation of the Metaform/TELEPORTRESS direction is **not “an AI game editor” and not “a 3D interface for coding.”** It is a spatial computing environment in which humans and autonomous agents share a world, share references inside that world, modify the world and its implementation, and can move between the *realized system* and the *structure that explains how it works*.

The supplied Metaform baseline already contains several unusually relevant primitives: agent bodies and viewpoints, structured spatial observation, user-view capture, pointer-ray and hit-target resolution, object manipulation, approach behavior, gestures, bubbles, speech, timers, and early child-agent/A2A work. Importantly, the baseline distinguishes what has actually been implemented or tested from what remains a proposal; independent child embodiment, complete piloting, general scene editing, physics, and game authoring remain gaps. fileciteturn0file0 The broader Metaform architecture also already treats MCP, ACP, and A2A as different layers rather than trying to make one protocol do everything, which becomes even more important once agents have persistent bodies, tasks, cameras, worlds, and project identities. fileciteturn0file1

My central recommendation is:

> **Do not transform the software graph into “the game world.” Build a common spatial substrate that can host multiple kinds of spaces—software maps, authored worlds, simulations, workshops, roundtables—and let stable Metaform identities connect them.**

That gives you the fascinating effect you described without forcing two fundamentally different spatial semantics into one representation. A door in a game can exist as a physical object in the world and simultaneously as a functional entity in Metaform. Entering its “implementation space” might reveal scripts, dependencies, events, tests, decisions, responsible agents, recent changes, and runtime traces. Selecting a dependency in the graph can take you back to the objects that instantiate it in the world.

Conceptually:

```text
                    METAform semantic plane
              stable identity · history · provenance
                         tasks · memory
                              │
             ┌────────────────┼────────────────┐
             │                │                │
             ▼                ▼                ▼
       Functional Map    World / Game      Other Spaces
       dependencies      scene / physics   simulations
       code / tickets    behaviors         workshops
       architecture      play mode         visualizations
             │                │
             └──── same identities ────┘
                              │
                     Humans + Agents
                  bodies · views · pointers
                  speech · tools · actions
```

That architecture is also directionally different from most current products. Unity now exposes an AI Assistant and MCP surface that can inspect scenes, edit scripts, trigger Editor actions, and access runtime/editor state; Roblox Assistant can create or modify scene objects and scripts, generate 3D content, simulate inputs and playtest experiences. Those are significant steps toward agentic game development, but their interaction model remains primarily “AI operates the editor.” citeturn5search5turn5search8turn5search0turn5search15 DeepMind's SIMA 2 pushes from the opposite direction: an AI can converse, reason and act within 3D virtual worlds, while Genie 3 provides interactive generated environments but explicitly identifies multi-agent interaction and sustained interaction as current challenges. citeturn1search13turn1search12

**The unexplored territory is the intersection:** an agent that is simultaneously *a participant in the world, a development collaborator, a software agent, a playtester, and a persistent member of the project.*

In the primary-source systems surveyed for this report, I did not find a public system combining all of those properties with a persistent software/functional graph and explicit human-agent spatial reference in one environment. That does not establish that no private or experimental system exists, but it suggests that Metaform's particular combination is meaningfully differentiated.

## The roundtable should be a collaboration protocol, not a group chat

Your “models sitting around a table with the user” idea is viable, but there is an important research result hiding underneath it: **more agents talking more often is not necessarily better.**

AutoGen demonstrated that multi-agent systems can combine models, human input and tools using configurable conversation patterns, and its later actor-based architecture explicitly supports asynchronous, event-driven agents rather than requiring a single serialized conversation. citeturn0search0turn0search1 Magentic-UI goes further toward the kind of mixed human-agent workspace you are imagining, emphasizing co-planning, co-tasking, multitasking and low-cost human participation rather than simply handing an entire job to autonomous agents. citeturn2search0

But Microsoft's 2026 *Collaboration Gap* work found that strong individual model performance does not reliably translate into strong multi-agent collaboration; some pairings degraded substantially, and interaction order mattered. citeturn8search0 Separate 2026 research on homogeneous multi-agent debate found failure modes including conformity and consensus collapse, with unguided debate sometimes using substantially more tokens while performing no better than isolated self-correction. citeturn8academia33 Research on agent sycophancy similarly finds that excessive agreement can prematurely destroy useful disagreement. citeturn8academia37

That strongly argues **against** a design where three embodied agents automatically answer every user utterance.

### A better model: listen, notice, offer, engage

I would make “participation” a state machine rather than a chat turn.

```text
                         ┌───────────────┐
                         │   OBSERVING   │
                         └───────┬───────┘
                                 │
                     detects useful contribution
                                 │
                                 ▼
                         ┌───────────────┐
                         │    NOTICE     │
                         │ private eval  │
                         └───────┬───────┘
                                 │
                 sufficiently novel / useful?
                    no ──────────┴──────── yes
                    │                       │
                    ▼                       ▼
                 remain                 OFFER
                 silent          "I have an idea here"
                                            │
                             user accepts / floor granted
                                            │
                                            ▼
                                         ENGAGE
                                            │
                                   act / discuss / test
```

The important property is that **silence is a valid successful output**.

A roundtable system prompt can express that very simply:

```text
You are one participant in a collaborative workspace containing a human
and other agents.

Observe the ongoing discussion and shared environment.

Do not respond merely because another participant spoke.

Contribute when you have a materially useful addition:
- a relevant fact others appear to have missed,
- a materially different interpretation,
- a concrete improvement,
- a detected problem,
- or an action you can perform that advances the work.

Prefer a short suggestion before a long explanation.

If another participant has already made your point adequately, remain silent.

When discussion concerns something in the shared environment, ground your
response in the referenced object or location when possible.

You may ask for the floor, point to something, demonstrate something,
or perform work instead of explaining it verbally.
```

That is substantially different from assigning fixed theatrical personalities such as “Architect Agent,” “Critic Agent,” and “Creative Agent.” Roles can still represent real expertise or responsibilities, but role-play should not be doing the architectural work.

A stronger roundtable pattern would allow each agent to independently form an initial view before seeing everyone else's suggestions, then expose only short claims or proposals for cross-review. That reduces the opportunity for early answers to anchor the whole group. This is an architectural inference from the documented collaboration and sycophancy failures rather than a proven optimal protocol. citeturn8search0turn8academia33turn8academia37

### Embodiment gives the roundtable something chat cannot

The bodies are not merely decorative avatars.

In multiparty interaction, gaze, pointing and gesture carry information about both reference and turn-taking. 2026 EACL work found gestures provide useful complementary information for modeling conversational turn transitions. citeturn3search0 MM-Conv, a 2026 benchmark built from egocentric VR interaction, combines synchronized speech, motion, gaze and 3D scene geometry specifically because natural references emerge from those modalities together. citeturn3search5 Ges3ViG similarly reports improved 3D reference grounding when language and pointing gestures are used together rather than language alone. citeturn3academia25

So the roundtable could have genuine spatial interaction vocabulary:

```text
human points → agent turns head toward target
agent wants floor → raises hand / subtle indicator
agent references object → points at it
agent is investigating → walks toward it
agent found problem → leads user's attention there
agent is busy → body moves to work area / status bubble
agent disagrees → short visible signal before verbal interruption
```

This can lower conversational clutter because some communication leaves the text channel entirely.

I would especially experiment with a **“whisper / suggestion / speak / act” hierarchy**. A weak observation appears as a tiny optional suggestion near the relevant object. A stronger contribution becomes a speech bubble. A direct request gives the agent the floor. An actionable task lets it simply start working.

That turns the spatial UI itself into the scheduler.

## Embodiment should combine vision with exact scene state

The most important technical observation in the current Metaform work may be the pointer ray.

A pure multimodal model looking at a rendered image can infer that the user “probably means the red box.” A spatially integrated agent can instead receive something like:

```json
{
  "utterance": "Can you move this next to the door?",
  "user_view": {
    "camera_id": "camera:user:rich",
    "position": [4.2, 1.7, -3.1],
    "forward": [-0.2, -0.1, 0.97]
  },
  "pointer": {
    "screen": [0.61, 0.44],
    "ray_origin": [4.2, 1.7, -3.1],
    "ray_direction": [-0.12, -0.08, 0.99],
    "hit_entity": "world:furniture:crate-017",
    "hit_position": [3.8, 1.1, 0.42]
  },
  "selection": null,
  "visible_entities": [
    "world:furniture:crate-017",
    "world:building:door-003"
  ],
  "frame": "<image>"
}
```

That is far more powerful than converting the world back into prose for the model.

The research literature increasingly supports exactly this combination. Modern 3D vision-language-action work is explicitly moving from 2D visual inference toward models that jointly represent 3D perception, reasoning, planning and actions. citeturn1academia37turn1academia39 Research on pointing-target estimation also increasingly models pointing as explicit geometry rather than expecting a generic visual transformer to discover the relationship implicitly. citeturn3academia24

For Metaform, you have an advantage over robotics: **you already own the virtual geometry.** You do not need to estimate the camera pose, object transform, ray intersection or object identifier from pixels when the renderer knows them exactly.

So an embodied observation should have two complementary channels:

| Observation | Purpose |
|---|---|
| Rendered agent-view image | Appearance, visual anomalies, materials, UI, emergent outcomes |
| Structured visible-object list | Exact entity identity |
| Camera transform | Agent perspective |
| Pointer/gaze ray | Exact shared reference |
| Raycast hit | Target identity and contact point |
| Distances/bearings | Spatial reasoning |
| Physics contacts | What the agent is touching/colliding with |
| Selection/hover state | Human attention |
| Runtime events | Doors opened, trigger fired, NPC entered state |
| Semantic Metaform links | What each world entity *means* in the project |

Your current supplied baseline already describes much of the first half of this stack—agent viewpoints, structured visible elements, user-view capture and pointer/hit information—while carefully noting that geometric observation does not by itself prove visual interpretation. fileciteturn0file0

That distinction should remain.

### Models should not drive the frame loop

The model should not decide:

```text
walk 1.8 cm
walk 1.7 cm
walk 1.6 cm
turn 0.7°
...
```

It should decide something like:

```text
approach entity door-003
face hinge-002
inspect
```

Ordinary code then runs path-following, collision avoidance, locomotion, animation and physics.

This matches both your current internal direction and the architecture of effective embodied systems: high-level reasoning chooses goals while lower-level control systems execute continuous actions. fileciteturn0file0 DeepMind's SIMA work similarly separates language-level goals from actions executed within real-time 3D environments. citeturn1search5turn1search13

The useful hierarchy is roughly:

```text
LLM / agent reasoning
        │
        │ "inspect the generator"
        ▼
semantic action planner
        │
        │ target = entity:generator-14
        ▼
navigation / interaction controller
        │
        ├── pathfinding
        ├── collision avoidance
        ├── animation
        └── manipulation
        │
        ▼
physics / rendering loop
```

The same architecture applies while the agent is *building*. The model says “place a support beam between these anchors”; deterministic code resolves anchors, creates transforms, validates geometry, updates physics and records an undoable scene operation.

### Event-driven perception is preferable to continuous inference

A browser can render sixty or more frames per second, but there is little reason to ask a large multimodal model to reinterpret all of them.

An agent can wake or reevaluate on events such as:

```text
pointer target changed
user selected object
user addressed agent
agent reached destination
collision occurred
runtime error appeared
build completed
test failed
object materially changed
another agent requested review
timer fired
```

Images can then be captured at meaningful moments.

This architecture also fits Microsoft's move toward asynchronous, event-driven multi-agent runtimes in AutoGen and the human-intervention model explored in Magentic-UI. citeturn0search1turn2search0

## The world and the software graph should be different projections of the same system

This is where I would make a fairly strong architectural decision.

**Keep the current Metaform map. Add inhabitable worlds alongside it. Then make traversal between them nearly instantaneous.**

The graph and game world have incompatible optimization goals.

A functional graph wants to expose:

```text
dependence
ownership
history
causality
implementation
tasks
changes
provenance
```

A game world wants:

```text
geometry
scale
physics
lighting
navigation
animation
interaction
sound
game rules
```

Forcing the graph to also be a physically meaningful game environment would eventually compromise both.

Instead:

```text
Functional entity: "security.door.west"
         │
         ├── represented by graph node
         │
         ├── implemented by:
         │      DoorController.ts
         │      AccessPolicy.ts
         │
         ├── instantiated as:
         │      world/entity/door-003
         │
         ├── behavior:
         │      behavior/locked-door
         │
         ├── tests:
         │      door-access.spec.ts
         │
         └── runtime traces:
                trace/...
```

The crucial piece is **identity**, not geometric co-location.

### Spatial teleportation becomes semantic navigation

Imagine pointing at a malfunctioning door.

The agent says:

> “The door is fine physically. The access state never transitions after the keycard event.”

It touches or points at the door and offers **Inspect implementation**.

The world fades into a spatial Metaform view centered on:

```text
                     Access Control
                          │
        ┌─────────────────┼────────────────┐
        ▼                 ▼                ▼
    Door Entity      Keycard Event    Player State
        │
        ▼
 DoorController
        │
        ▼
  failing test
```

You and the agent can move around that representation, inspect the failing test, edit the behavior, run it, then step back through the doorway into the game.

That is not merely “3D source visualization.”

It creates a direct spatial relationship between:

> **experience → implementation → modification → experience**

This is, in my view, the most compelling form of the TELEPORTRESS idea.

### Use a canonical editable scene model, not the renderer as the database

Three.js should remain a renderer/view layer, not the authoritative world representation.

I would introduce a stable scene entity model roughly like:

```text
World
  id
  revision

Entity
  id
  parent_id
  transform
  components[]
  asset_refs[]
  functional_refs[]
  behavior_refs[]
  provenance
```

Edits become explicit operations:

```text
CreateEntity
DeleteEntity
SetTransform
SetComponent
AttachBehavior
DetachBehavior
SetProperty
ReparentEntity
LinkFunctionalEntity
```

That gives both humans and agents the **same editing language**.

Undo then becomes an ordinary property of the edit log rather than a special case for AI-generated modifications.

For asset interchange, glTF is already the standard runtime-oriented 3D delivery format, and Khronos submitted `KHR_interactivity` for ratification in July 2026 to carry portable behavior graphs inside glTF assets. citeturn9search0turn9search1 That makes glTF highly attractive for portable authored objects and reusable interactive assets.

OpenUSD addresses a different layer: large-scale scene authoring and composition. USD layers can be stacked, referenced and overridden non-destructively, and its composition model exists specifically to support large collaborative 3D production pipelines. citeturn10search2turn10search9 NVIDIA's Omniverse Live workflow demonstrates concurrent live editing using USD layers and even independent live sessions on sublayers or referenced prims. citeturn10search15

My architectural inference is therefore:

**Prototype:** internal Metaform scene model + Three.js + glTF assets.

**Later interoperability:** glTF import/export for playable assets; optional OpenUSD gateway for professional scene/DCC workflows.

I would not make USD the core browser data model initially. Its power is compelling, but it solves a much larger production-composition problem than the first Metaform world prototype needs. citeturn10search7turn10search2

### Multiplayer editing and gameplay state should not be the same synchronization problem

Yjs provides CRDT-backed shared maps, arrays and other collaborative data types that merge concurrent modifications automatically. citeturn9search16 That makes it a reasonable candidate for shared editor metadata, text, object properties, graph annotations, conversational artifacts or scene-document operations.

I would not use CRDT replication as the physics engine.

For moving characters and simulated objects, use an authoritative world simulation and transmit snapshots/events. For persistent authored changes, use transaction/revision semantics and, where useful, CRDT structures.

That separation will matter once multiple humans and agents are manipulating the same environment.

## A practical browser-native architecture is already within reach

For the initial system, staying browser-native is technically plausible.

Rapier explicitly supports JavaScript/WebAssembly, 2D and 3D rigid-body simulation, ray queries, shape casts, contact events and optional cross-platform determinism. citeturn9search14turn9search10turn9search13 Since your existing Metaform world is already Three.js-based and already relies heavily on ray-based spatial interaction, Rapier is the least disruptive first physics experiment.

Jolt is the stronger candidate to evaluate when workloads become substantially more game-like. Its upstream engine is designed for games and VR, and the official JavaScript port exposes WASM builds including multithreaded variants. citeturn11search0turn11search2 It is also a somewhat heavier integration surface in JavaScript, including explicit WASM-side object lifetime management. citeturn11search2

Box3D is newly interesting in 2026. Erin Catto's upstream engine provides continuous collision, character movement, ray/shape queries, multithreading, determinism, recording and replay. citeturn11search12 Browser WASM packaging exists, but the browser ecosystem around it is younger than the mature Rapier path or Jolt's official JS port, so I would measure it rather than select it from feature lists alone. citeturn11search3turn11search12

The comparison should therefore be empirical:

| Workload | Measure |
|---|---|
| One human + several embodied agents | frame time |
| Hundreds/thousands of static colliders | query latency |
| Character movement through clutter | controller stability |
| Agent raycasts | query throughput |
| Dragging dynamic objects | contact quality |
| Twenty to hundreds of rigid bodies | simulation cost |
| Browser reconnect / replay | reproducibility |
| Worker/WASM integration | engineering complexity |
| Scene serialization | recovery fidelity |

My default starting point would be **Rapier first, Jolt as the serious alternative, Box3D as the experimental contender**. That is a prototype recommendation, not a benchmark result.

### The development loop should happen inside the world

The killer workflow is not “ask AI to generate code.”

It is:

```text
refer
  ↓
inspect
  ↓
edit
  ↓
run
  ↓
experience
  ↓
observe
  ↓
explain
  ↓
iterate
```

Current Unity and Roblox tooling demonstrates that agents can already manipulate scenes, scripts and playtesting through structured editor interfaces. Unity's 2026 MCP integration provides project and scene hierarchy, GameObjects, component values, console information and Editor actions to an external agent. citeturn5search8 Roblox says its Studio Assistant can create and modify objects/scripts and that its MCP server lets an external MCP client read, edit and playtest a place. citeturn5search0turn5search15

Metaform can take that model one step further:

> **The agent using the editor can be physically standing in the scene it is editing.**

That opens surprisingly natural workflows.

You point at a bridge:

> “It needs to collapse if more than four people stand on it.”

The agent can inspect the bridge entity, locate its behavior, edit or generate the component, enter play mode, bring several test bodies onto it, observe whether the collapse occurs and tell you what happened.

Then another agent can review the implementation without everybody leaving the spatial environment.

### Authoring agents and runtime characters should be the same embodiment system but different roles

This distinction is essential.

A development agent may have:

```text
world perception
scene editing
source editing
tests
build tools
project memory
Metaform graph
```

A runtime NPC may have:

```text
world perception
movement
dialogue
game actions
character memory
authored knowledge
```

A playtesting agent might sit between them:

```text
world perception
game controls
runtime logging
bug reporting
Metaform ticket creation
```

They may share the same body/camera/navigation implementation while having radically different capabilities.

NVIDIA ACE is already pushing game characters beyond dialogue into characters that perceive, plan and act within games. citeturn4search4 SIMA 2 similarly demonstrates agents that converse and pursue goals inside diverse 3D worlds. citeturn1search13 Neither fact implies that developer agents and NPCs should collapse into one role; rather, it demonstrates that the embodied action side of the architecture is becoming technically credible.

## Identity and protocol boundaries matter more once agents have bodies

The current Metaform work correctly recognizes a subtle issue: a visible child-agent figure is not necessarily an independently embodied child if its tool calls still resolve through the parent's identity. fileciteturn0file0

That problem becomes foundational in a real shared world.

I would define a protocol-neutral actor identity structure before doing much more embodiment work:

```text
ActorInstance
    actor_instance_id

    agent_definition_id      // what kind of agent
    runtime_session_id       // current ACP/model session
    project_id
    world_id
    body_id
    camera_id
    conversation_id
    task_id
    parent_actor_id?         // lineage, not identity
```

Every spatial operation should resolve from `actor_instance_id`, not from “whatever session happened to call the tool.”

```text
actor ───── owns ─────► body
  │                     │
  │                     └────► camera
  │
  ├──── participates ──► world
  ├──── works on ──────► task
  └──── converses in ──► session
```

That internal identity model should remain independent of ACP, MCP and A2A.

MCP's July 2026 specification makes this particularly important because MCP is now explicitly stateless: persistent state must be represented using explicit identifiers rather than inferred from a protocol session. citeturn7search0turn7search5 In other words, **MCP should transport `body_id`, `world_id` or another explicit handle; it should not own them.**

ACP should represent the interactive agent session. ACP standardizes editor/agent interaction, and current Codex ACP support includes multimodal content plus negotiated native child sessions with separate child histories. citeturn6search0turn6search4 ACP v2 is now in draft and is explicitly expanding the set of session states it can represent. citeturn7search2

A2A belongs one level farther out. Its Agent Card describes agent identity/capabilities and its task model provides remote work lifecycle and artifacts. citeturn7search3 That makes it suitable for:

```text
local embodied architect agent
      │
      │ A2A task:
      │ "produce candidate terrain mesh"
      ▼
remote terrain-generation agent
      │
      ▼
artifact returned
      │
      ▼
local architect places it in world
```

The remote agent does **not** need a body in the local world unless you explicitly choose to represent it there.

That separation keeps embodiment from becoming protocol spaghetti.

## The most revealing prototypes are small

I would avoid starting with “build a game engine.”

The question to answer first is whether **spatial grounding actually changes the quality of human-agent development.**

The following experiments are small enough to be decisive.

| Demonstrator | What happens | What it proves |
|---|---|---|
| **Point and change** | User points at one of several similar objects and requests a modification | Spatial reference is reliable |
| **Agent show me** | Agent discovers a defect and walks/points the user to it | Agent-to-human spatial reference works |
| **Inspect → edit → play** | User points at interactive object; agent edits behavior and runs it | Development loop works |
| **Embodied playtester** | Agent plays scene, reproduces bug, records object/code linkage, retests fix | Runtime and development worlds connect |
| **Quiet roundtable** | Three agents observe design session but only contribute novel suggestions | Multi-agent collaboration is useful without chatter |
| **World ↔ graph teleport** | Select game object, enter its functional implementation space, then return | Core Metaform/TELEPORTRESS thesis is understandable |
| **Two independent bodies** | Parent and child/peer agent independently see, move, point and act | Identity architecture is real |

The spatial-reference experiment deserves unusually rigorous measurement.

Construct scenes with increasing ambiguity:

```text
easy:
    red cube / blue sphere

moderate:
    three similar doors

hard:
    dense machinery with overlapping sightlines

very hard:
    moving objects + occlusion + multiple agents
```

Then compare four conditions:

```text
text only
image only
image + pointer overlay
image + structured ray/object identity
```

Measure:

```text
referent-selection accuracy
distance from intended hit
clarification rate
incorrect edit rate
time to successful action
tokens / model calls
```

If the ray/object identity condition does not dramatically outperform screenshots alone, something is wrong in the embodiment stack.

Current 3D grounding research gives good reason to expect multimodal geometric reference information to help, but the actual gain in Metaform should be measured rather than assumed. citeturn3academia25turn3search5

### The roundtable experiment should test silence

Give one design problem to:

```text
one model
three models speaking freely
three models with fixed turn-taking
three models using "only novel contributions"
three heterogeneous models with independent initial opinions
```

Measure:

```text
useful ideas accepted by human
duplicated ideas
interruptions
time
model calls
token cost
human-rated cognitive load
changed decisions
errors caught
```

The interesting metric is not “number of ideas.”

It is something closer to:

> **useful marginal contribution per interruption.**

This directly tests the concern raised by multi-agent collaboration research instead of assuming agent quantity equals intelligence. citeturn8search0turn8academia33

### The playtester experiment could become a killer feature

A particularly compelling early demonstration would be:

1. The user builds a simple room with a door, switch and moving platform.
2. An embodied agent receives a goal such as “reach the balcony.”
3. It physically plays the game.
4. It fails because the door event is broken.
5. It says where it got stuck and points to the door.
6. The user asks it to investigate.
7. It traverses from the door's runtime entity into its Metaform implementation context.
8. It modifies the behavior.
9. It returns to play mode.
10. It succeeds.

No individual piece is science fiction anymore. Current agents can operate 3D worlds; current editor assistants can modify scene/code state; current spatial-language research can ground references; current agent infrastructure can orchestrate tool use. citeturn1search13turn5search8turn5search15turn3search5

**The innovation is composing the pieces around persistent shared identity and spatial grounding.**

## Where this could lead

The near-term product might look like collaborative game development, but I would keep the underlying architecture more general.

A “world” could be:

```text
a game
a software architecture
a network topology
a factory simulation
a building
a data center
a scientific simulation
a training environment
a digital twin
a collaborative design space
```

Metaform supplies the persistent functional and provenance layer; the spatial runtime supplies embodiment, perception and action.

That is why I would resist describing this simply as “AI game creation.”

The bigger abstraction is:

> **A shared executable space in which people and software agents can perceive the same things, refer to the same things, modify those things, understand how they work, and test the consequences together.**

World-model research is moving toward interactive, persistent 3D environments; Genie 3 now demonstrates real-time interactive world generation, while persistent embodied-world-model research explicitly explores spatial memory across long-horizon action. citeturn1search12turn1academia38 Multi-agent world-model research is also beginning to address independently controllable agents sharing one evolving generated environment. citeturn1search3 Those approaches are largely concerned with generating or simulating worlds, however.

Metaform has a different opportunity: **make the world inspectable and editable as software.**

That is a much stronger proposition.

The progression I would pursue is:

| Stage | Capability | Proof |
|---|---|---|
| Grounded embodiment | Human and agent reliably refer to the same objects | “this one” works |
| Independent agents | Each agent owns body, view and session | two agents can separately inspect |
| Quiet roundtable | Agents collaborate without flooding the user | useful marginal suggestions |
| Shared scene editing | Human and agents manipulate identical object model | every edit is visible and undoable |
| Behavioral authoring | Objects have code/graphs linked to Metaform | select object → inspect behavior |
| Play loop | Scene executes immediately | edit → play → observe |
| Embodied testing | Agent experiences resulting application | agent reproduces failures |
| Graph/world traversal | Runtime entities and functional model interconnect | world ↔ implementation |
| Multi-human world | More than one person joins agents | shared creation |
| External agent federation | A2A peers contribute work/artifacts | remote collaborators appear when useful |

This also answers the “map or separate world?” question fairly decisively:

**Both—but as different spaces connected by identity rather than one space awkwardly pretending to be both.**

Let the existing Metaform map become the first member of a family of inhabitable semantic spaces. Let TELEPORTRESS provide the more general world/runtime capability. Let an agent retain identity, memory, body and task as it crosses between them.

A human could then say:

> “Show me why this elevator behaves this way.”

The agent points at the elevator.

> “The timing comes from this subsystem. Come with me.”

And instead of opening another chat window, another editor and another debugger, you both **go there**.

That is the part of this idea that appears genuinely unusual—and the current Metaform embodiment work means it is no longer merely a metaphor. fileciteturn0file0