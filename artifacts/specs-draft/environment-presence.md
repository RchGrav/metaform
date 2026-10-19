# Design and draft record: agents present in any environment

Draft for Rich, 2026-10-14. Nothing is in `specifications/` yet. The record number is a placeholder. The questions at the end are open.

## The design

### The problem
Metaform now has several places an agent can be in: the map, where agents have bodies and the `web_*` tools; the roundtable, with seats, `rotate`, `look` and the push of each turn to the head agent; and next, the physics playground. Each one built its own way of telling an agent what happens and letting it act. None of them lets an agent simply be present: take in what happens as it happens, stay silent, and act or speak when it chooses. An agent today acts only when it is handed a turn or a ticket.

### The idea
Presence is one capability of Metaform, the same in every environment:
- **An environment** is anything a module provides that agents can be in: the map, a roundtable, the physics world, a document being written together, a game.
- **An environment publishes what happens in it as events,** and offers controls an agent can use there.
- **An agent attaches to an environment** and from then on receives its events in its own session, as they happen, in order. On each event the agent decides: do nothing, speak, or act through the environment's controls.
- **The agent is the only judge of what matters to it.** Metaform delivers; it never decides for the agent.

### What already exists to build on
- **The event bus** (`src/metaform/events.py`, BASE-010, BASE-032/033): modules publish topics, subscribers receive them, and `map.changed` crosses processes (BASE-053).
- **Delivery into a running agent session:** dispatch's `message` (BASE-052). The roundtable already pushes each turn into the head agent's session with it.
- **Bodies and controls on the map:** `web_go`, `web_move`, `web_turn`, `web_look`, `web_see`, `web_embody`. And at the roundtable: `rotate`, `look`, `look at`.
- **Agent identity:** the runner session (`METAFORM_SESSION`), and the A2A sender identity (MCP-042).

### What is new
1. **An environment contract in the module declaration,** beside `Verb` and `Noun`. A module declares an environment: its name, the event topics it publishes, its controls (verbs), and how an agent attaches and leaves. `modules/template` shows it.
2. **Attach and leave,** one pair of verbs for every environment. An agent can be attached to more than one environment at once.
3. **Delivery:** each event of an environment an agent is attached to goes into the agent's session as a message, in order, none skipped, numbered so a restart neither skips nor repeats. The environment never waits for the agent's answer.
4. **The agent's answer:** nothing, which is valid and costs nothing more; or calls to the environment's controls, which publish new events that others receive.
5. **Who it is:** every event carries who caused it, and every control acts as the calling agent's own identity and body, never another's.

### What it costs, and why that is accepted
Every event an agent receives is one model call, even when it does nothing. That cost is the price of real presence: the agent itself hears everything and decides. No cheap model filters on its behalf. The person sees the cost per agent and per environment, and sets the caps (how long an agent may stay attached, how much it may spend).

## Draft record

### BASE-0P1 An agent can be present in any environment: it receives what happens there as it happens and acts when it chooses

- **Requirement:** Any module can provide an environment. An agent attached to an environment receives every event the environment publishes, in its own session, as each happens, in order, and on each one decides for itself whether to do nothing, speak, or act through the environment's controls.
- **What this means:**
  - **An environment is declared by its module:** its name, the event topics it publishes, the controls agents use in it, and its attach and leave. The template shows how.
  - **Attaching** is one verb for every environment, `presence attach <environment> [scope]`, with `presence leave`. An agent may be present in several environments at once. Who may attach to what follows the environment's own rules; the roundtable's seats and chair, for example.
  - **Delivery:**
    - Each event is delivered into the agent's running session as a message, in order, none skipped.
    - Delivery is numbered per agent and environment, so a restart neither skips nor repeats.
    - The environment never waits for the agent.
    - An agent that is busy when events arrive receives them in order once it is free.
  - **The agent decides.** Doing nothing is a valid answer. Nothing filters or summarises events on the agent's behalf.
  - **Identity:** each event names who caused it; each control acts as the calling agent, through its own body in that environment.
  - **Limits the person sets:** how long an agent stays attached and how much it may spend while present. Reaching a limit detaches it and says so.
  - **The roundtable becomes the first user of it.** The head agent's push of every turn is presence in the roundtable environment. The map and the physics playground follow.
- **Why:** Agents that act only when handed a turn cannot take part. They miss what happens between their turns and cannot choose their moment. Presence makes an agent a participant in whatever environment it is in, and making it one capability means every environment, present or future, gets it the same way rather than each inventing its own. The agent's own judgment is the filter, because only the agent knows what it has to add; a cheaper model deciding for it would replace that judgment with a guess.
- **Acceptance:**
  - An agent attached to a roundtable receives every turn as it lands, once and in order, and can stay silent.
  - The same agent attached to the map receives the map's events (a node changed, another agent moved near it, someone spoke to it) and acts with its body controls.
  - Leaving stops delivery.
  - A restart resumes delivery with nothing skipped or repeated.
  - A limit reached detaches the agent and tells the person.

## Open questions for Rich
1. Is an environment's event stream everything that happens in it, or what the agent's body can perceive there (in sight or in earshot), in environments that have bodies?
2. Who may attach agents: only the person and the head agent, or any agent to itself?
3. What does the person see of presence: which agents are attached where, and what each spends?
