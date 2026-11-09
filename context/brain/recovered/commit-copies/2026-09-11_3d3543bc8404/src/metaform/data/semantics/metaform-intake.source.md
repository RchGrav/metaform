> **Superseded intake procedure.** This preserved source describes the historical v1 dual-pass procedure. New v2 intake uses `../roles/composition.json` and publishes one Native foundation; requested outside reasoning receives the complete Native account and attaches knowledge. The original source below is retained for provenance.

# Metaform Intake

This specification governs the dual-pass Intake procedure. It uses the canonical ontology and storage meanings defined by the Metaform Core. Chassis and module contracts may define how the procedure is scheduled, transported, persisted, or exposed, but they do not change what the Native Expert, Latent Expert, or merge means.

Intake is the first step of amortizing inference in a repository. It produces the project's Inference Metaform: a dual-perspective reified knowledge graph built by two agents that never share context, then merged by the Metaform system.

The method is typology as archaeology practices it, without chronology. Archaeological typology sorts artifacts into types by function and style, not by when they were made. Metaform does the same to a namespace. Function joins purpose. Encounter joins style. Every member of the Namespace is a Type. The concrete workpiece is evidence for the native pass, but it is never stored as an Artifact Type. Independently named records are stated at the level of their Types, while native joins retain how those Types participate in the current workpiece.

---

## Part 1 — Developer instructions

This section describes how the Metaform system runs the intake workflow. It is not agent prompt text.

### Actors

- **Orchestrator agent.** Starts the workflow. Makes sure the repo is ready. Does not perform inference and does not see either subagent's context.
- **native subagent.** Born in the repo. Runs in the project root with fresh, non-shared context. Produces the local layer.
- **Latent Expert.** Runs in a Metaform temp folder with fresh, non-shared context. Starts only after the autochthonous subagent completes. Produces the typological layer.
- **Metaform CLI.** Runs the intake workflow. Accepts, recomposes, merges, and saves.

### Context

Both subagents receive the full glossary in Part 3 in their context. Neither subagent receives the orchestrator's context. Neither subagent receives the other's context.

The Native Expert receives its context the same way Metaform passes context when it creates a work folder or worktree: through `<project>/.agentid/nonce`.

The Latent Expert receives its context in the Metaform temp folder. It receives the native objects one at a time with the native OP relationships removed. NS, EN, ED, optional aliases, and other non-OP object fields remain. It does not receive repository files, the native OP join table, or repository-specific prose outside those structured object fields. The Latent Expert can use the Metaform CLI or MCP Namespace search, which resolves project-local and global Namespace objects as one candidate surface.

### Sequence

1. The orchestrator makes sure the repo is ready and starts the intake workflow.
2. Metaform starts the Native Expert in the project root with fresh context and the glossary.
3. The Native Expert performs the local pass (Part 2). For each dependency it uses one Metaform CLI or MCP Namespace search; Metaform searches local and global objects together and returns one candidate set. New Namespace objects are authored locally.
4. The Native Expert submits its finalized data structure, including NS, EN, ED, optional aliases, and native OP joins.
5. The Metaform CLI accepts the structure as submitted and holds it as the native layer of the Inference Metaform.
6. Metaform adds each newly authored Namespace object from local to `~/.metaform/inference/metaform.kg`, preserving its non-OP object data and omitting the native OP relationships.
7. Metaform recomposes the native structure into individual object handoffs. Each handoff contains one Native Expert object with its native OP relationships removed; NS, EN, ED, optional aliases, schema-governed non-OP fields, applicable schema, and inference purpose remain.
8. Metaform starts the Latent Expert in a Metaform temp folder with fresh context, the glossary, and the first object. Objects are processed one at a time.
9. The Latent Expert performs the typological pass (Part 2) using pure inference without knowledge of the project and returns its own shape for each object.
10. Metaform stores the latent inference-produced categorical inference and latent OP joins against the reusable global Namespace objects.
11. Metaform copies the required global records and latent OP joins into the workpiece graph. The existing native OP joins remain intact beside them.
12. Metaform matches the native and latent inference graphs by Namespace Scope and creates merged relationships where their independently authored OP joins describe the same relationship. The source OP joins remain present and separately attributable.
13. Metaform saves the workpiece-specific graph in the repo. For a non-repo task, Metaform saves it to `~/.metaform/inference/{encoded_filesystem_path}/metaform.kg` so non-repo work stays separate from global data.

### Determinism

Metaform makes the orchestration, context separation, local-to-global node promotion, record projection, and merge procedure deterministic by construction. Each subagent gets a bounded task, fresh context, and the glossary. The orchestrator cannot pass its own framing into either pass. The Latent Expert cannot see the repository or native OP joins, but it does receive the Native Expert object's NS, EN, ED, aliases when present, and other non-OP fields. Semantic inference remains model inference. The merge is a Metaform operation over separately attributable records and relationships, not an agent judgment.

---

## Part 2 — The typological process

### Local pass (the autochthonous subagent)

The Native Expert born in the repo abstracts the project to its Artifact Type. It starts from one of four base types — `code`, `document`, `media`, `data` — and adds modifiers one at a time. Each modifier is the simplest, most common elemental that fits, always tuning for the shortest namespace. Read the address right to left: `code.game.engine` is an engine, of a game, in code.

Before adding or resolving a Namespace object, the Native Expert performs one search through Metaform CLI or MCP. Metaform filters across project-local and global Namespace objects and returns one candidate set; the Native Expert does not search the stores separately. The Native Expert dumps the candidate information and uses a Type whose EN, ED, and EF fit. If no candidate fits, it authors a new local NS object and completes its EN, ED, and optionally one or two aliases only if warranted.

With its Type named, the Native Expert lists the Elements of that Type in the coarsest useful sense. It adds an OP join to satisfy each dependency one at a time, from the Element bearing the OP to the linked Element that provides the EF it receives. A Notable Element can be named because Elements address it or because it is a dependency without thereby becoming Defining. A Defining Element is named and abstracted into an Artifact Type for latent inference. Parametric Elements remain compact. The Native Expert stays broad and shifts focus as required by the typology.

Two rules end the walk. A Notable Element can remain internal to the root Artifact Type even when it is named because another Element addresses or depends on it. When further naming exposes no additional relationship needed by the typology, naming stops.

Last, if a Stylistic Element — genre, mood, style — better describes the type, the Native Expert names it and links its encounter to the root's OP. Its effect permeates through every encounter it joins to the Operative Purpose of the upstream Receiving Entity.

Every Namespace object gets an EN and an ED: the most common and concise name and description of it as its Type. They are used for inference. The Native Expert independently authors its native OP joins in the local graph; those joins name the Receiving Entity bearing the OP and the linked Element whose EF that OP is for. Native OP relationships remain separately attributable and are projected into the join surface when the record is committed. New Namespace objects are created locally; Metaform promotes them to global after local work ends with the native OP relationships removed from the promoted copy. The local native OP joins remain intact.

### Typological pass (the Latent Expert)

The Latent Expert receives the Native Expert's objects one at a time with their native OP relationships removed. NS, EN, ED, optional aliases, and other non-OP schema fields remain. It is blind to the repository and does not know which native OP relationships caused the object to participate in the project.

It works through the same typological procedure as the Native Expert using pure inference without knowledge of the project. It can query the composed Namespace through Metaform CLI or MCP to reuse existing objects. For each Type it builds the one EF and independently authors its own latent OP joins, each naming the Receiving Entity bearing the OP and the linked Element whose EF that OP is for. It then names dependencies and considerations in the most general specific terms it can without project bias.

It returns its own shape in the same graph representation as the local pass, with latent inference provenance. The latent OP joins are stored globally as reusable categorical inference.

### Merge

The two shapes become one repository or workpiece-local graph with three relationship scopes.

- **Native OP.** Independently authored by the Native Expert in the workpiece-local layer. It stays workpiece-local. The Namespace object may be promoted globally, but this OP join is not.
- **latent inference OP.** Independently authored by the Latent Expert in the global layer. It is retained globally as reusable categorical inference and is copied intact into a workpiece graph when that global inference is brought down.
- **Merged OP.** The same receiver-to-EF-owner relationship and relationship category are present in both layers. The workpiece-local reified relationship retains both OP statements and their provenance in addition to the two source OP joins; it does not replace either source join.

Function joins purpose. Encounter joins style. The Inference Metaform is a pliable non-manifold semantic mesh formed from the named Elements and the RE/OP/EF functional structure around them. It preserves concise Type descriptions, each linked Element's EF, RE → OP relationships, major Elements, dependencies, stylistic effects, and the native, latent inference, and merged relationships needed for later inference.

### Worked example: `code.game.engine`

**Local pass.** The agent reads the repo and abstracts. Base type `code`. Modifier `game`. Modifier `engine`. Address: `code.game.engine`. The namespace has it. EN, ED, and EF match. The agent uses it.

Elements, coarsely. Types whose EF the engine has an OP for: `code.game.physics`, `code.game.rendering`, `code.game.audio`, `code.game.input`. Types that have an OP for the engine's EF: `code.game.logic`, `code.game`.

Shift focus to `code.game.physics`. Its collision system: gameplay queries depend on its EF, so it is a Notable Element, `code.game.physics.collision`. The dependency is enough to name it, but does not by itself make it Defining or require an latent inference pass. Its integrator remains internal and is described inside physics. `timestep`, `gravity`, `restitution`: Parametric Elements, listed in a simple array. Physics has no OP for any type not yet named. Naming stops.

Stylistic Element. The project is a platformer. The agent names `code.game.platformer` and links its encounter to the engine's OP. It changes the encounter of physics (jump arcs), rendering (side view), and input (run and jump), and permeates to the player's Operative Purpose: to play the game.

Native graph excerpt:

```json
{
  "elements": {
    "code.game.engine": {
      "entity_desc": "code that runs a game's simulation, rendering, audio, and input each frame",
      "entity_schema": "metaform.artifact-type.example",
      "entity_json_obj": {
        "en": "game engine",
        "parametric_elements": ["fps", "tick_rate"]
      }
    }
  },
  "joins": [
    {
      "object_id": "code.game.engine",
      "join_scope": "native",
      "element_id": "code.game.physics",
      "type": "receiving_entity",
      "purpose": "simulate motion and collision so the game can be played",
      "schema_id": "metaform.join.example",
      "join_logic": "the game engine has an Operative Purpose for the physics Encounter Function"
    },
    {
      "object_id": "code.game.logic",
      "join_scope": "native",
      "element_id": "code.game.engine",
      "type": "receiving_entity",
      "purpose": "have the engine execute the game's rules",
      "schema_id": "metaform.join.example",
      "join_logic": "game logic has an Operative Purpose for the engine Encounter Function"
    },
    {
      "object_id": "code.game.engine",
      "join_scope": "native",
      "element_id": "code.cpp",
      "type": "dependency",
      "purpose": "implement this repository's engine in C++",
      "schema_id": "metaform.join.example",
      "join_logic": "this repository uses C++ to implement the engine without making C++ part of the categorical engine Type"
    },
    {
      "object_id": "code.game.platformer",
      "join_scope": "native",
      "element_id": "code.game.engine",
      "type": "stylistic",
      "purpose": "shape joined encounters toward run-and-jump play",
      "schema_id": "metaform.join.example",
      "join_logic": "the platformer style changes the encounter of joined game Elements"
    }
  ]
}
```

The excerpt omits the parallel native joins to rendering, audio, input, and the game container only to keep the example compact. Their direction follows the same rule: the Artifact Type that owns the OP is `object_id`, and the Artifact Type that owns the EF is `element_id`.

**Typological pass.** The Latent Expert receives the Native Expert's objects selected for latent inference one at a time, each with its native OP relationships removed. The object retains its NS, EN, ED, optional aliases, and other non-OP fields. It receives no repository files or native OP joins. `code.game.physics.collision` remains a named Notable Element in this example rather than being promoted to latent inference solely because another Element depends on its EF.

For `code.game.engine` it builds the EF: a runtime loop that other game code calls each frame. It independently authors the latent OP joins for that EF, including game logic having an OP for the engine to execute the game's rules and the player having an OP to experience a running game. It names what any engine type must define: `code.game.physics`, `code.game.rendering`, `code.game.audio`, `code.game.input`, `code.game.asset`, `code.game.scene`. It walks `code.cpp` back to `code` and defines it as its own type with no join to engines, because a language is not universally an element of an engine.

**Merge.**

| Join | Kind | Statements |
|---|---|---|
| `code.game.engine` → `code.game.physics` | Merged | native: simulate motion and collision so the game can be played. Latent inference: advance body state and resolve contacts each tick. |
| `code.game.engine` → `code.game.asset` | latent inference-only | an engine loads and manages assets. The repo has not named this. |
| `code.game.engine` → `code.game.scene` | latent inference-only | an engine organizes what is active in the world. The repo has not named this. |
| `code.game.engine` → `code.cpp` | Native-only | stays in the repo layer. Never enters `code.game.engine`'s global record. |
| `code.game.engine` → `code.game.platformer` | Native-only | Stylistic Element. Stays in the repo layer as the project's genre join. |

The latent inference-only joins are independently reusable categorical inference. The Native-only joins are what this workpiece contributes. When the required global inference is copied into the workpiece graph, its latent OP joins are retained beside the existing Native OP joins. The merged joins are additional repository-owned compositions that retain both perspectives without replacing either source join. Together they form the project's Inference Metaform. Newly authored Namespace objects have already been added from local to `~/.metaform/inference/metaform.kg` without their native OP relationships; latent inference adds and retains its own categorical OP joins there. The complete workpiece-local graph, including copied global records, latent inference joins, Native joins, and Merged joins, stays with the workpiece.

---

## Part 3 — Glossary (in context for both subagents)

* **Element:** A thing that is capable of being named, identified, or worthy of note. A who or what that is internal or external and tied to an Artifact Type, including the Artifact Type itself. Elements include components, relationships, settings, quantities, qualities, subparts, Receiving Entities, functions, purposes, encounters, joins, signals, and procedures.
* **AT: Artifact Type:** A coarse graph object consisting of structural shape that describes the shared properties of an Element's type, establishing the structural criteria for an Inference Metaform model. These properties create a metaform of the workpiece type that can amortize inference by lexicalizing workflows and converting abstract concepts into imperatives that live in a reified knowledge hypergraph structure.
* **DT: Digital Typology:** Describes the expert process of arranging the Elements of a workpiece into a graph of nodes and edges, where encounter joins style and function joins purpose, creating one of the two layers of an Inference Metaform.
* **RE: Receiving Entity (The "Who" or "What" bearing an OP):** The person, group, system, component, or other participant with an Operative Purpose for the Encounter Function of an Element when classifying its typology as an Artifact Type. A Receiving Entity can be internal or external to the Artifact.
* **EF: Encounter Function (The "How" Description):** The mechanism, interface, relationship, or method through which an Artifact or Element performs its purpose for its Receiving Entity. It explains how the effect is delivered, encountered, used, or experienced.
* **OP: Operative Purpose (The "Why" Join):** The objective, value, or intended effect that drives an Artifact or Element's function for its Receiving Entity. It explains why the Artifact or Element exists at the level currently being examined.
* **ET: Element Table:** A table keyed by ID (namespace string), with fields for `entity_desc`, `entity_schema`, and `entity_json_obj`.
* **ED: Element Description:** The most common and concise description of an Element when examined as its Artifact Type. This is not decorative; it is used for inference.
* **EN: Element Name:** The most common and concise name of an Element when examined as its Artifact Type. This is not decorative; it is used for inference.
* **NS: Namespace Scope (Only Alpha and Periods):** The unique scope of all Elements, excluding Elements that answer to who, Parametric Elements, and the actual reified joins. The four base valid types are `code`, `document`, `media`, and `data`.
* **DE: Defining Element:** An Element that is named and abstracted into an Artifact Type and then analyzed by the Latent Expert, whose job is to analyze its Type's identity, Operative Purpose, Encounter Function, and Receiving Entity.
* **NE: Notable Element:** An internal Element with its own boundaries and surfaces for change. It carries the identity of an internal subsystem, but it does not carry the identity of the root Artifact Type. It is named because Elements address it or because it is a dependency of other Elements.
* **PE: Parametric Element:** A quality or quantity that can be tuned by changing a value. It does not have a specific named identity in individual Artifacts of that Type. It lives in a simple array and uses a one-word or `snake_case` name.
* **SE: Stylistic Element:** An Element that imbues a distinctive nature that groups others in the class or Type that share this quality. SE does more than describe function; it tangibly changes the encounter of Elements it is joined with, and that effect permeates all the way through to the Operative Purpose of the upstream Receiving Entity beyond the Element it is directly joined with. Genre is like this.
* **Native Expert:** A task-focused agent purpose born in a project folder for the sole purpose of mapping its relational, functional, and stylistic typology. It identifies the project's Defining Element and describes the functional Elements at the Type level, whether implemented in the project or supplied by a framework. It does so by constructing a coarse yet precise graph starting with the DE's NS, EN, ED, and OP joins to receive the EF provided by a linked element. The Native Expert must add an OP join to satisfy each dependency one at a time. To do so the Native Expert must determine if the NS of the element already exists by filtering the object list using Metaform CLI or MCP, then dumping the info of candidates. If no match is found, it authors a new, local NS object, completes its EN, ED, and optionally one or two aliases only if warranted. When complete it may join SE where needed with a transitive join that will travel through to the DE.
* **Latent Expert:** An expert typology agent who receives the Native Expert's objects one at a time without any OP, who works through the same procedure as the Native Expert using pure inference without knowledge of the project. When complete the two graphs are merged by matching the NS with fields indicating the source of every OP and the resulting reified knowledge hypergraph is populated deterministically as the Inference Metaform layer of the project-specific `metaform.kg` SQLite3 file.
* **Inference Metaform:** A pliable non-manifold triangle mesh comprised of a double blind semantic structure that acts as a navigation layer of a reified knowledge hypergraph enabling contextual join rubrics for thresholds and conditions to control agentic workflows, meaning expansion via metaform prompting imperatives, project targeted imperatives and knowledge extraction via unbiased inference, unlocking advanced refactoring capabilities, porting projects from one language to another, creating photo processing pipelines, written story structure analysis, enhancing agent creativity, enforcing operation completeness, and more. (That's only what we have tested!)

