Metaform: embodied agents, shared 3D applications and game creation
Research seed, 13 October 2026. This is an envisioned direction and evidence-based capability baseline, not an implementation specification.

Envisioned goal
Develop a shared spatial environment where people and agents can observe, navigate, communicate and create together. An agent has a controllable body and viewpoint, can inspect its surroundings and the person's view, understand what the person is pointing at, manipulate represented objects, and explain its work through gestures, word bubbles and optional speech. People can direct its actions, while the agent can choose movement, attention and follow-up timing.
Extend this from Metaform's functional map into collaborative 3D applications and eventually a visual game editor. A person and agents could assemble scenes, attach behavior, run them, observe results and improve the work. Establish A2A team collaboration before expanding into game authoring.

Current foundation and evidence
The live environment is Metaform's interactive 3D functional map, rendered using Three.js with graph layout. Its scene sits alongside persistent project context, tickets, memories and agent conversations.
Live observation in this conversation established that the scene is accessible through tools, an image can be returned from the mascot/agent viewpoint, and the person's current camera position, direction and visible elements can be read.
Newer capability tickets #11, #12 and #14 have completed builder handbacks and reported focused tests. Reviewed source contains the corresponding implementations. These are stronger evidence than proposals, but not independently demonstrated end-to-end product acceptance. The current live web_viewing response still has the earlier camera-only shape: reloading the page and refreshing tools in an agent session may be needed to exercise additions.

Implemented capabilities
- Bodies and viewpoints: animated figures represent active agents; a conversation agent can obtain a character, inspect its own field of view and receive a rendered image.
- Structured observation: the agent can read visible elements, distances, bearings, selected/active state and nearby figures. These geometric observations are not proof of correct visual interpretation.
- Direction and manipulation: tools move, turn, point, gesture, select, push, drag and release objects, and control views. Piloting currently means directing bodies and viewpoints through these operations and user instructions. A complete game-style human input controller has not been demonstrated.
- Shared visual attention: current source adds the 3D pointer position, world-space ray and the actual target a click would take, with no-hit/exit/project-change handling. Capture draws the pointer reference into the image.
- User-view capture: source=view renders from the person's 3D camera. It captures the rendered scene; it should not be described as a complete screenshot of every browser interface overlay.
- Shared-screen capture: source=screen takes a frame from a tab, window or display the person selected through getDisplayMedia. Frames return as MCP image content to the asking agent, or accompany a selected chat session's ACP prompt when image capability is declared. Real desktop sharing in the person's browser and real-adapter image receipt remain explicit handback verification gaps.
- Approach behavior: agents can approach the camera, the pointer in the view or the pointed-at graph location. They can choose duration and whether to follow, and end an approach. The current implementation is for 3D.
- Communication: word bubbles, gestures and expressions exist. Speech requests reuse the person's voice configuration. Local/browser speech and optional voice-provider modules are implemented integration choices; not every provider was demonstrated in this review.
- Timers: an agent can set, list and cancel a timer that wakes its own session with a note. These timers are owned by the runner and end with the session.
- Native subagents: recorded ACP child sessions can appear as separate 3D figures and open their own threads. Actual Claude adapter child-session records were reported as evidence; native children are not fabricated tickets.

Material gaps
A child's figure and thread are separate, but its MCP calls still carry the parent's identity. It cannot yet be described as independently controlling its own body, perception and image recipient. The handback also leaves 2D child figures, real-adapter replay and an empty subsequent-generation thread unresolved.
Timers do not survive runner restart. 2D pointer/approach parity is not delivered. Full human piloting controls, arbitrary application editing from screenshots, physical collision-aware movement, a general scene editor and game authoring are future work in this review.
Screen access, scene-state access, input injection and application-specific editing are different capabilities. A screenshot does not itself provide an editable scene or desktop control.
The functional graph's layout/forces are distinct from a game physics simulation. No selected rigid-body engine or complete game-runtime integration was demonstrated.
A2A preparation reports real loopback HTTP exchanges between two isolated temporary services: assignment, artifact, review and follow-up. Deterministic fixture owners produced the outputs. This proves protocol behavior, not a shipped outbound peer/team feature or live-model collaboration. Peer configuration, verified sender identity, durable exchange correlation and integrated team presentation remain work.

Suggested development stages
1. Reliable embodiment: complete caller/body/view ownership, exact visual and structured pointer correspondence, refresh/reconnect behavior and truthful lifecycle. Demonstrate that a person can point, ask about the target and receive a spatially correct response from the intended agent.
2. Agent teams: establish independently addressed A2A peers, bounded assignments, returned artifacts, review and follow-up. Keep ACP session execution, MCP tool access and A2A peer exchanges distinct. Demonstrate an actual two-agent round trip on existing tickets and views.
3. General spatial applications: provide module hooks for scene objects, transforms, selection, action execution and visual observation. Preserve project/work references while each application owns its editable scene. Start with one object shared between a user and an agent, with undo and observable results.
4. Physical interaction: evaluate Rapier, box3d.js or JoltPhysics.js with the same workload. Demonstrate approach, obstacle avoidance, object contact and ray/shape queries. Keep continuous physics and animation in ordinary code; agents choose goals and bounded actions.
5. Visual game authoring: provide a shared scene editor for objects/assets, properties, physics, behavior and play mode. Both user edits and agent actions operate through the same editing model. Start with one small playable scene and an inspect-edit-play-observe-improve loop. Visual behavior graphs versus scripts remains an open authoring choice.
6. Game inhabitants and simulation teams: explore agents as participants, NPCs, guides, playtesters and collaborators inside authored applications. Evaluate runtime agents separately from agents building the game. Extend toward multi-user or XR environments only where shared presence and coordinate registration justify them.

Concrete possibilities
A spatial project assistant can approach the code or design object under the person's pointer, explain a dependency and show where a change applies.
A collaborative scene editor can translate 'move this beside that' into a grounded edit, preserving object identity and exposing the change to both people and agents.
A simulation assistant can run experiments, observe outcomes, annotate the objects involved and compare runs while another agent reviews the findings.
An embodied playtester can navigate the actual game, identify a reproducible problem, connect it to scene/mechanic/code context and retest a correction.
A game character can react to events, remember encounters and use authored world state in dialogue. This is a future design opportunity, not a current demonstrated ability.
Remote A2A peers could contribute assets, reviews or simulation results while the user follows their actual responsibility and progress in a shared interface.

Execution and inference
Separate continuous rendering/physics, bounded structured judgments and longer reasoning. Camera transforms, ray casts, animation, collisions and deterministic gameplay should execute locally in code. Larger reasoning can select goals, plan edits and interpret ambiguous evidence. Optional focused models such as TypeSafe/Jev could judge relevance, references or response choices from structured text state. Current Jev docs specify text-only inputs; visual interpretation would need another supported model. Latency, uncertainty and cost must be measured in the actual workload.

Deep Research assignment
Use the supplied baseline to investigate viable architectures and opportunities for this progression. Verify external technical claims against current primary sources. Do not claim to have audited private repository files you cannot access. Preserve the distinction between live observation, implementation/test evidence, isolated protocol proof and proposals.
Research how to:
- Combine images, scene state and pointer rays for reliable shared reference.
- Bind agent, session, body, camera, project, task and child identities across MCP, ACP and A2A.
- Support tool-driven and direct human piloting without conflicting motion controllers.
- Design gesture, bubble, speech and sound interaction and measure usefulness versus interruption.
- Ground manipulation in scene identity and preserve undo, references and concurrent edits.
- Choose event-driven perception and action timing instead of model inference every frame.
- Compare physics engines and browser/native capture using measured workloads and delivery requirements.
- Build a modular shared editor that both people and agents can operate.
- Evaluate gameplay/runtime agents separately from developer assistants.
- Establish persistence and recovery boundaries for timers, tasks, memories, artifacts and embodied sessions.

Ask the research to return a staged roadmap, current examples and primary sources, candidate architectures with tradeoffs, small demonstrable experiments and measures of spatial correctness, task completion, recovery, latency, cost and user experience. Mark ideas, evidence and decisions separately.

Primary external references
ACP content/image capabilities: https://agentclientprotocol.com/protocol/v1/content
Native subagent extension and adapter limits: https://github.com/agentclientprotocol/codex-acp/blob/main/docs/subagent-sessions.md
A2A: https://a2a-protocol.org/latest/specification/
Screen Capture API: https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getDisplayMedia
Rapier controllers: https://rapier.rs/docs/user_guides/javascript/character_controller/
Rapier queries: https://rapier.rs/docs/user_guides/javascript/scene_queries/
Box3D browser bindings: https://github.com/isaac-mason/box3d.js
Jolt browser bindings: https://github.com/jrouwe/JoltPhysics.js
TypeSafe System One and text-only input: https://docs.typesafe.ai/concepts/system-one

Internal evidence
Metaform GUI tickets code.interface.graphical#11, #12, #14; A2A preparation code.dispatcher.agent#5; reviewed web/__init__.py, web/page/app/figures/eyes.js, attention.js, agents.js, dispatch/runner.py and mcp/a2a.py. Structural pointer trace confirmed pointerRay and hitAt feed pointerNow, consumed by seenBy, viewing and capture. Source generation/freshness was checked; no runtime suite was rerun for this report. Several current feature handbacks describe uncommitted work.