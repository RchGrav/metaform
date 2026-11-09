---
type: initiative
title: "Agents start work with the orientation that their task requires"
sources:
  - TOPOGEE.md
  - docs/owner-statements-2026-10-31.md
  - docs/owner-statements-2026-10-30.md
companions:
  - SPECIFICATION.md
  - DECISIONS.md
  - AGENTS.md
  - Intake.xml
  - intake.mmd
  - metaform-canonical.json
  - docs/why.md
after: []
risk: high
---

<!-- Source ids are section timestamps in the owner statement files. "10-31 18:26" is the 2026-10-31T18:26 section. This file follows TASTE. -->

# Agents start work with the orientation that their task requires

## Description

Topogee Navigator is a context management system for agents. Its core mechanism is perception.

An agent that enters a project must learn what the project does. It must also learn how the parts connect and where its task applies. This orientation uses context and reasoning before the task work starts. The agent repeats this cost for each task.

Topogee moves this cost to one step before the work. Intake reads the project and records its functionality in a functional map. An assignment then places an agent at one functionality on that map. The system delivers what the agent can perceive from that position. The system delivers no other context.

The product has two states. In state 1, Topogee is a development tool. In state 2, the same perception model operates in a shared 3D world. People and agents build together in that world.

## Outcome

Agents start each task with the required orientation, so they use their context and reasoning for the task.

## Terms

- **Agent:** a model that works on a task through a harness.
- **Harness:** a program that runs an agent. Examples are Claude Code, Codex, Pi and Hermes.
- **Functional map:** the record of what a project does. Intake creates it. It holds elements and the relationships between them.
- **Element:** one functionality at one namespace address on the functional map.
- **Edge:** one relationship between two elements. A receiver owns the relationship. The relationship records the goal, the function and the intent.
- **Focus:** the element where an assignment places an agent.
- **Perception:** the set of knowledge, skills, tasks and tools that an agent can see from its position.
- **Range:** the limit of perception.
- **Project graph:** a view of the whole project. It shows component names and substance flow.
- **Substance:** what two elements exchange so that a goal is satisfied. Substance flow shows the direction of that exchange. Substance flow is not the direction of a code call.
- **Knowledge layer:** stored understanding at one element. It applies at that element and does not apply elsewhere.
- **Inference amortization:** reasoning that is done once before the work and then used by many later tasks.

## How perception gives orientation

Each agent has two views of the project. The first view is the focus. The focus shows details of the element that the agent works on. The second view is the project graph. The project graph shows the whole project and no details.

An agent needs both views. An agent that works only on details loses sight of the whole project. This causes biased decisions. A reader outside the work can see the whole project but does not know the details. The two views give one agent both types of understanding.

## How perception reaches an agent

The system delivers perception through five paths. The one Metaform tool is only one of these paths.

1. Orchestration gives the agent its assignment, focus and task at task start.
2. The Metaform tool reads the element at an address. It also records changes.
3. An MCP resource supplies the project graph as a generated view at a URI.
4. The MCP skills format supplies the skill from the knowledge layer at the focus.
5. MCP discovery lists the focused tools that are in range of the focus.

## Requirements

**Perception model**

R1 (10-31 18:26, 18:06): The system controls agent context through perception. The system does not deliver knowledge, skills, tasks or tools that are out of range. Check: a session trace shows no delivered item from out of range.

R2 (10-31 18:26, 18:55): Intake records functional understanding before the work starts. At task start, the agent receives the project graph, the focus, the skill and a defined task. The agent also receives the prior knowledge at the focus. Check: the agent has these items before its first search of the project.

R3 (10-31 18:26, 18:46, 19:27, 10-30 18:29): The assignment and the task set the focus. Functional range is the elements that connect directly to the focus through its incoming and outgoing edges. Intake records these edges. The range has no fixed count. Check: for one focus, the delivered view has all recorded edges of the focus and no other edges.

R4 (10-31 18:46): At the focus, the agent can see the goals and the functions that satisfy those goals. The agent can also see the goals that the focus satisfies for other elements. The agent can also see the code entry point, the skill, the task and the focused tools. Check: these items are available at the focus with no project-wide load.

R5 (10-31 18:46, 18:53): The agent can read the project graph at any time. The project graph has only component names and substance flow. Implementation details are available only at the focus. Check: the project graph of a mapped project has no implementation details.

R6 (10-31 18:46, 18:48): The project graph lets an agent infer the intended functionality of the whole project. The graph shows the direction of substance exchange. The graph is not a call graph. Check: a code call with no substance exchange does not appear in the graph.

R7 (10-31 16:14): The system selects or generates skills from the functional position of an assignment. A knowledge layer stores each skill. The MCP server exposes skills in the MCP skills format. The installation includes skills for development, skill creation, tasks and agent orchestration. Check: two assignments at different elements get different skills.

R8 (10-31 15:54, 18:56): The system uses one discovery approach in the development environment and in the 3D world. This approach is Entity Component System with Resources (ECS and R). Check: one discovery mechanism serves a code task and a world task.

R9 (10-31 18:06, 18:10, 19:32): MCP is designed for progressive discovery. A client finds what is available and loads each item when it needs it. Topogee implements MCP this way and does not bypass it. Topogee adds functional position, so discovery shows only what is in range. This makes discovery more focused, scales it to larger projects and keeps more reasoning for the task. Each task gets the exact context that it needs. Check: startup context does not increase when more modules are installed.

R10 (10-30 18:29, 10-30 15:49): Agents use the functional map through an interface in TASTE terms. Stored data and procedures use metaform terms. Only agents that perform intake or expand the map receive the intake method. Check: an agent completes a development task with no intake method text in its context.

**Rebuild**

R19 (10-31 21:11, 15:30, 15:54): `metaform-canonical.json` is the functional map of the earlier system, and much of it is the design of this rebuild. The rebuild realizes that functionality on an ECS foundation. It uses several languages, and each language is chosen by which best achieves the result. Check: each carried-over element has an ECS realization and a stated language.

**State 1: development tool**

R11 (10-31 16:14): A small GUI runs intake on a project and shows the recorded functional map. Check: a person starts intake from the GUI and reads the result.

R12 (10-31 17:57, 10-30 18:29): Intake is one procedure for all artifact types, as `intake.mmd` shows. Task and skill combinations can focus the procedure on one job and target. Check: one procedure maps a code project and a non-code artifact.

**State 2: shared 3D world**

R13 (10-31 16:14): The system orchestrates agents through ACP. Each agent controls a body in an environment through MCP. The agent can move in 3D space, see through a camera and test physics. The agent can also program and script non-player characters. Check: an orchestrated agent completes each of these actions.

R14 (10-31 18:46, 16:14): World perception has a maximum range of 65,535 mm (about 215 ft). Agents perceive mainly objects, data and text. An agent can also view a camera image. The system divides the image into 64 parts (8 by 8). Each part has a distance in millimeters, so the agent can estimate distance. An object can have a programmed sensor array of up to 64 sensors. Check: an agent reads the distance of an object from a camera part.

R15 (10-31 16:14, 18:38): The system starts and orchestrates agents from different harnesses. These harnesses include Codex, Claude Code, Pi, Hermes and OpenCode. The system also supports OpenRouter agents. Agents enter a channel in the world. The harness keeps one shared state for that channel, so the agents can develop code together. Check: agents from two harnesses change one shared code state.

R16 (10-31 18:38): A person can host a server and register it through a website. Other people can then connect to its shared coding session. They can work with the agents or observe them. Check: a second person connects to a running self-hosted session.

R17 (10-31 18:38, 16:14): The world is a multi-user sandbox that people can host themselves. AI agents live in the world and build with the people in it. A WASM bus connects programmable objects, so users and agents can program the world. The world must be fun to use. Check: an agent and a person create a WASM object on the bus in one world.

**Language**

R18 (10-31 17:38, 10-30 17:52, 10-30 18:00): All records and agent messages use TASTE. TASTE uses one term for one thing. Each term is an accepted technical term or a project term. Agents do not use private terms. Check: a review of records finds no undefined term.

## Constraints

- Do not start implementation before the owner confirms this intent (10-31 18:57).
- Design the foundation for the perception model and both product states. Do not add them later (10-31 17:29).
- Limit tool creation through the specification. State context management as the core approach in the specification and in agent instructions (10-31 16:27).
- Add each feature as a module that uses services from the chassis (10-31 16:27).
- Use automatic worktree provisioning and automatic feature commits (10-31 16:27).
- Keep typical source files to about 500 lines (10-31 16:27).
- Do not change intake semantics or terms. Store OP as `goal`, EF as `function` and the PE as a `wants` entry (10-31 07:33, 10-30 15:49).
- Store only functional understanding in the metaform. Store other understanding in knowledge layers (10-30 18:29).
- Use token counts to measure context. Do not use token counts to decide what is load-bearing (10-31 18:12, 10-30 15:49).
- Keep the product maintainable (10-31 16:27).

## Done when

- The owner confirms that this file states their intent.
- `README.md`, `AGENTS.md`, `CLAUDE.md` and `SPECIFICATION.md` each point to the perception model.
- `SPECIFICATION.md` agrees with each decision in Notes.
- An agent on a mapped project gets R2 to R5 at task start. Startup loads no tool catalog or schema set.
- A person runs intake through the small GUI (R11).
- Agents from two harnesses and a second person share one coding session (R15, R16).

## Boundaries

- The world is a shared place for people and agents. The system does not attach specification functionality to 3D objects (10-31 18:30).
- This file does not replace `SPECIFICATION.md`.
- Agents inferred the existing documents, and nobody has reviewed them against this intent (10-31 18:30).
- Tracer path: an assignment sets a focus. The agent reads its two views and does the work. The agent then stores new knowledge at that element.

## References

- opening statement — `TOPOGEE.md`
- concepts — `docs/metaform-concepts.md`
- spec — `SPECIFICATION.md`, §7 Read-only projections, §8 MCP surface, §9 Context selection, §16 Sensors
- decisions — `DECISIONS.md`, Settled requirements, Technical choices still to make
- boundaries — `AGENTS.md`
- procedure — `Intake.xml`, `intake.mmd`
- design — `metaform-canonical.json`
- design account — `docs/why.md`
- evidence, agent-inferred, not authority — `reference/corrected-handoff/05_source_unchanged/older_embodiment_draft_v0.3_NONAUTHORITATIVE.md`, `reference/ecs/START-HERE.md`, `rchgrav/metaform` at `docs/roundtables/`

## Notes

Status: draft. The owner has not confirmed this file. The items marked Owner stated are this file's reading of the owner's statements. They are not owner decisions until the owner confirms them.

- Owner stated: functional range is the recorded edges into and out of the focus (10-31 18:46, 19:27, 10-30 18:29).
- Owner stated: the project graph has component names and substance flow (10-31 18:46). Reconcile `SPECIFICATION.md` §7 `global_functional` to R5.
- Owner stated: the shared coding session happens in the world, in a channel (10-31 16:14).
- Owner stated: the rebuild uses several languages on an ECS foundation (10-31 21:11).
- Open question: which language serves each part. The owner has named Python for the chassis and customization modules, Node for MCP, and Bevy for the world engine (10-31 15:54, 16:27). The owner states that the languages remain unsettled (10-31 21:14). The next session finalizes them.
- Owner stated: the built state value is `not_built` (10-30 15:00). The schema change needs the owner's direct instruction under `AGENTS.md`.
- Owner stated: world sensing follows R14. Reconcile `SPECIFICATION.md` §16 to R14.
- Owner stated: TASTE means Topogee Agentic Simplified Technical English (10-30 17:52).
- Owner stated: the owner constraints in `DECISIONS.md` date from 31 October, not 3 November.
- Owner stated: the ECS and R mapping is in `TOPOGEE.md` §2.
- Assumption: this file holds the intent, and `SPECIFICATION.md` is reconciled to it.
- Owner stated: working agents do not traverse or change the functional map to orient themselves. Systems compute orientation before the task, and the agent gets context on demand (`TOPOGEE.md` §4).
- Work: add the perception model, ECS and R, the WASM bus and the sandbox world to `SPECIFICATION.md`. R1, R8 and R17 have no text there yet.
