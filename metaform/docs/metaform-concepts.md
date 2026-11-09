# What Metaform is

Metaform is a perception-based context management knowledge engine for AI agents. It does the work of understanding a project in advance, keeps that understanding, and gives each agent exactly the part it needs for its task.

The aim is simple. An agent should spend its reasoning on the work, and should not have to spend it on finding out where it is.

This document explains the problem, the idea, and the key concepts. It is written for a person or an agent who knows nothing about the project. Read it from the start, because each concept depends on the ones before it.

The architecture is in `TOPOGEE.md`. The founder's own words are in `docs/owner-explanations.md`. Where this document and those words disagree, the founder's words govern.

## The problem

When an agent arrives at a project, it knows nothing about that project. It must search files to learn what the project does, how the parts connect, and where its task applies. This orientation is not a small task. It uses context and reasoning before any real work starts.

The agent repeats this cost for every task. What it learns ends with the session, so the next agent starts from nothing.

Three failures follow from this:

- **Gaps get filled with guesses.** If the project does not tell the agent the names, functions and reasons, the agent invents them. The invented answers sound as confident as the correct ones.
- **Work goes wrong or stays incomplete.** The agent has used its capacity on orientation before the work starts.
- **Agents lose the whole.** An agent deep in a task sees details and loses sight of what the project is for.

## The core idea

The central question of the project is this: what reasoning can be done in advance, so that an agent does not have to do it during the work?

The answer has three parts:

1. **Do the understanding once.** A procedure called intake works out what a project is and how its parts serve each other.
2. **Keep it in a usable form.** The result is a functional map. The map stores conclusions about what things are for.
3. **Deliver it by position.** Each agent works from a position on the map and perceives what is in range from there. Nothing else reaches it.

## Key concepts

### Inference amortization

Amortization means paying a cost once and then using the result many times. Metaform pays the cost of understanding a project up front. Every later task then uses that result and does not pay the cost again.

This applies only to reasoning that an agent would have to do in any case, such as learning what is there. It does not replace the reasoning that the task itself requires. It does not make a model more capable. It gives the model better use of the ability it already has, because less of that ability goes to orientation.

The main saving is reasoning effort. Token count is a separate measure. A smaller context is not the goal in itself. The goal is the exact amount of context that the task needs.

### Functional understanding

The map records functionality: what each part does and why it exists. It does not record the programming language, the file layout, or other non-functional properties.

This is what makes the map stable. Code changes, files move, and languages change. The purpose of a part changes much less often. Five agents can perform intake on the same project and produce five different maps, and each map is still solid and grows with the project.

Because functionality is not limited to code, the same method works on any artifact: a code base, a story, a film, a photograph. In a story, a character has a function in the story. In a photograph, the subject has a function in that image.

### Addresses and type understanding

A model already understands kinds of things: engines, queues, game engines, photographs. This understanding exists before the model sees any project. The founder calls it primordial type understanding.

Each functional element has a namespace address, such as `code.engine.game.fps`. The address names a functional type. Read in reverse, it gives a name: first-person game engine code. Each prefix is also a complete type, so `code.engine.game` is game engine code.

An address is therefore more than a storage key. It is a prompt in itself. The founder proved this with four prompts of the form "write 10 best practices for [address]", with no project supplied. The addresses were nearly identical, and the four lists hardly overlapped. Most of the inference came from the last segment, and the earlier segments held it in the correct domain.

Practices attached at a parent address apply to everything below it. This one-way inheritance is how one prompt can be magnified across a whole project.

The rules for addresses are strict. `code.engine.game.fps` is valid, because first-person play is a real functionality. `code.engine.game.platformer` is not valid, because platformer is a genre. These rules apply only to intake and to expansion of the base map.

An address is not a name. The `name` field holds what the project calls that functionality. The founder's example is `document.dialect.project`, which reads as project dialect, and whose name is TASTE.

### The functional map

The map is a nested tree of elements. Each element lives at its address and owns its own properties and knowledge.

Elements connect through relationships. A relationship belongs to the element that needs something. That element is the receiver. The element that provides it is the provider. An element is a receiver in one relationship and a provider in another, so these are perspectives and not two kinds of thing.

Each relationship records three things:

- **goal:** what the receiver needs to achieve. Intake calls this the Operative Purpose (OP).
- **function:** how this provider satisfies that goal in this relationship. Intake calls this the Encounter Function (EF).
- **intent:** the substantial flow of information which satisfies the (OP) goal not including the request: send, receive or send_receive. Intake calls this the Information Flow Direction (IFD).

For example, an email client wants an email server. The goal is to send and receive mail. The function is the email server service. The intent is send_receive.

Every chain of relationships traces back to the Cestui Que Use (CQU). This is the type of party with a vested interest in improving this kind of artifact. The term is unusual on purpose. Plain terms lead models to answer "the user" or "the developer", and those answers say nothing about the artifact.

### Exact identity

A functional type is defined by its exact set of relationships: who receives the effect, why they need it, and how it is delivered. The formula is `C(T) = { (r_i ∧ p_i ∧ e) }`.

This separates two kinds of change. Mutation changes how something is built and keeps what it is. Transformation changes what it is. An agent can refactor or port code and know which of the two it is doing.

### Intake

Intake is the procedure that creates the map. It is one universal procedure for every artifact type. It surveys the artifact, traces what each element needs, recurses through the requirements, closes gaps, combines parts, and proofs the result. It also records what is built and what is not built yet, so that every later process knows what exists.

The intake terms are deliberately ambiguous. They are contextual anchors, tuned and tested across frontier models. A term resolves to a precise meaning only in the context of the operation. This is why the method must not be reworded. An agent that improves the wording pulls the method into its own register. Code intake still works, the loss stays silent, and about half of the benefit to agents disappears.

Most agents do not need this method in context, and it would hurt them. Specialist agents carry the method. All other agents use its result through an interface, in plain terms.

### Knowledge layers

A knowledge layer is understanding that matters in one part of the project and does not matter elsewhere. It is stored at the element it concerns. Skills, memories, tasks and notes all live this way.

Knowledge therefore has a location. When an agent works at an element, it finds what earlier agents learned there. This is how knowledge passes from one agent to the next without a long shared history.

Stored knowledge is not always active knowledge. Selection decides what takes part in a given operation.

### Perception

Perception is the core mechanism. What an agent knows depends on where it is.

An assignment and its task place the agent at a functionality on the map. This position is its focus. From the focus, the agent perceives:

- the goals of that functionality
- the functions that satisfy those goals
- its own function, and the goals it satisfies for what relies on it
- the code entry points, the skill, the task and the focused tools

The range is the set of elements directly connected by the edges into and out of the focus, as intake recorded them. Knowledge outside that range does not reach the agent. A network engineer on a job site does not need to know what the plumber is doing.

### The project graph

The agent can also see the whole project as a graph. The graph shows only the names of the components and the flow of substance between them.

Substance is what two parts exchange so that the project works. Its flow is the direction of that exchange. It is not the record of which code calls which. From names and flow, an agent can infer the intended functionality of the whole project.

### Two views against bias

Intelligence has biases, and bias comes from being too close to a problem. A person deep in a problem knows the particulars and cannot see the answer. A person outside can see the answer and does not know the particulars.

Metaform gives one agent both views. At the focus, it sees all the detail of what it works on. In the project graph, it sees the overall functionality and no detail. It can work on the particulars and also judge them against the whole.

### Progressive discovery and MCP

MCP is designed for progressive discovery. A client finds out what is available, then loads each item when it needs it. Metaform implements MCP this way, and it adds functional position. Discovery shows what is in range for the work at hand.

Tools, skills and tasks are therefore things an agent perceives at a location. They are not a list that it receives at startup. This is what keeps the system usable as a project grows.

Skills also follow position. When an agent gets an assignment, the system selects or generates the skill for that part of the functional topology. The skill lives in a knowledge layer and reaches the agent through the MCP skills format.

### ECS and Resources

Entity Component System (ECS) is the way game engines organize a world, and Bevy adds Resources for shared data. A system in ECS does not see the whole world. It sees what it asks for.

The same discovery pattern serves two places: what is in perceptual range in Topogee's 3D world, and the context Metaform delivers in the development environment. Perception is one approach in both.

### TASTE

TASTE is Technically Accurate, Simple, Transparent English, the project's writing rules, adapted from ASD-STE100. Think of it as being for communication what code smell is for code.

Models paraphrase, and they write from inside their own reasoning, as if the reader shared their context. In a system where agents hand work to each other, this spreads errors. An agent also cannot tell its own context from shared context.

TASTE has one rule at its center: there is no "my word for it". There is the accepted technical term, or the project's term, and each term has one meaning.

## The two products

This repository develops two products (`DECISIONS.md`, "Naming: Topogee and Metaform").

**Metaform: the development tool.** Metaform maps a project and gives agents perception of it. A small GUI runs intake. Metaform orchestrates agents through ACP, and agents work through MCP.

**Topogee: a shared world.** Topogee is a world where agents and people collaborate and build anything, including the world itself. Its design is `docs/designs/world-system-spec.md`. The same perception model extends to a 3D world. An agent can position itself in space, see through a camera, test physics and program non-player characters. World perception is range-limited to 65,535 mm, or about 215 ft. Agents mainly perceive objects, data and text. A camera image divides into 64 parts, and each part has a distance, so an agent can estimate distance.

The world exists so that people and agents can work together. A person can host a server, and other people can connect to a shared coding session. Agents from any harness, such as Claude Code, Codex, Pi or Hermes, can enter a channel and develop code together in one shared state. The world is also meant to be fun: people build in it as they do on a Minecraft server, with AI agents in place of mobs, and with a WASM bus in place of redstone, so that everything is programmable.

## What went wrong last time

The earlier build was stable for about two months. Every feature landed as a module on a Python chassis, through services that the chassis exposed. That design worked and stays.

The failure was in the tool surface. The specification did not constrain tool creation, and the core approach of context management was not stated clearly. The tool count grew to about 300, and all of those tools and their schemas loaded at startup. The first orchestration test used a full week of inference allocation. Agents also got direct access to the backend data and treated the system as a database to maintain.

The whole design of this system is the fix for that failure. Measurement only shows what is used. The fix is that an agent never receives what is out of its range.

## What Metaform is not

- It is not a code index or a call graph. It records purpose.
- It is not a way to attach specifications to objects in a 3D world. The world is a shared place for people and agents.
- It is not a smaller prompt for its own sake. The target is the exact context for the task.
- It is not an interface for agents to maintain a database.
