# Digital Archeology

# Purpose
Define and construct a minimal, coarse project memory graph shape for an artifact or a specification by identifying its categorical notable elements and joining them through type specific Operative Purposes.

# Core Concepts
- **Artifact**: The actual thing being examined, created, or used. Artifacts can include photographs, contracts, stories, resale assets, and software. The work can concern multiple artifacts and projects. Whether an artifact serves as an asset depends on its use in that context.
- **Element**: An entity that is capable of being named, identified, or worthy of note within the understanding of an artifact. (Note: Entities are elements, joins are elements, not all elements are entities. An element is a namable thing of consideration, while entities are objects which are in the elements under consideration.)
- **Join**: A dictionary object that exists in the RE with a relation in active voice, an observation as an atomic fact that is present in all artifacts of its type; additionally it contains a dictionary of objects containing type specific or artifact specific references and logic.
- **RE — Receiving Entity**: The "who" or "what" bearing an OP. This is the person, group, system, component, or other participant with an Operative Purpose for the Encounter Function of an Element. The OP belongs to that receiver.
- **EF — Encounter Function**: The "how" description. This is the mechanism, interface, relationship, or method through which an Artifact or Element performs its purpose for its Receiving Entity. It explains how the effect is encountered, used, or experienced.
- **NS — Namespace Scope**: The unique scope of all Elements, excluding Elements that answer to who, Parametric Elements, and the actual reified joins. The four base valid types are `code`, `document`, `media`, and `data`.
- **OP — Operative Purpose**: The "why." This is the active why an encounter function is meant to satisfy. This represents the JOIN between elements in the graph. It is the only element in the graph which can speak directly to the artifact; all other elements must speak to a common encounter function type which may be understood in many artifacts, not just this one.
- **NE — Notable Element**: An element of this artifact whose categorical role must be named in order to understand the minimal shape.
- **DE — Defining Element**: The notable element of this artifact whose loss would prevent the artifact from remaining the same type. Its Encounter Function summarizes the combined result of the artifact being examined. Its defining function is expressed independently of medium, encoding, genre, and style.
- **SE — Supportive Element**: Any notable element of this artifact which is entangled with the encounter of the Defining Element in such a way that if omitted, the artifact would not remain the same type.
- **PE — Providing Element**: Any element which exists in the full cached namespace enumerated from the Native Metaform, or the Inference Metaform (recursively enumerated from aliases and joins in the Native Metaform) itself.

# Namespace Rules
For each dotted part, the address in the namespace must be reversible and read as its name. Namespace entries must describe the type of functional approach.

Examples:
- `code.loop.main` = main loop program code
- `code.bus.data.event` = event data bus code

To be placed into the namespace, an entry must be the same thing as its parent type, or a function within its parent type, without being a non-functionality based variant.
- Children must take their parent’s name as their last name when reversed and read as a noun.
- Specify the name_length value indicating the lookback segment count as its acceptable short name that is well understood.
- The segments in the namespace can be reversed by replacing periods with spaces to read properly as an inferenceable, well understood name.
- It must be a part or type of its parent scope.
- Namespace must narrow from trunk to leaf.

Note: This is a typological ontology, it is not a taxonomy. It does not have fillers like domain and class, and it does not prescribe a minimum or maximum segment count per entity.

## Namespace Validity Examples
- `code.game` — invalid; game is not a function
- `code.game.engine` — almost valid if it refers to an external game engine as an SDK
- `code.engine.game` — valid; this represents game engine program code. `game engine` is legal because it is a functionality type enabled by an external SDK identified by that exact name, "game engine"
- `code.engine.game.fps` — valid as a functional subtype; this is a load-bearing valid example of a distinct functionality. Initial intake references this via a join as a major core functionality in `code.engine.game` from `code.engine.game.fps` as a supportive element. (Proof: first-person camera viewpoint with a targeting reticle)
- `code.engine.game.platformer` — invalid as a functional subtype; this is a load-bearing invalid example with a concrete reason: it defines the fundamental challenge and objective of a game, not a technical functionality. (Proof: spatial navigation and overcoming environmental obstacles)
- `code.engine.game.doom` — invalid; not a function or type. The name is a specific game and cannot be used as a type or subtype element.
- `media.image` and `media.asset.image` — both valid. Images are assets when they are not the actual artifact being examined, for example when a member is a sprite sheet. However, the inverse is not true: assets are not all images in this context.
- `media.photo` — valid; this represents photo media
- `media.photo.jpg` — invalid; this is encoding
- `code.cpp` — invalid; this is language
- `document.word.story.conflict` — invalid; `word` is naming an encoding and does not name a functional approach at the proper namespace level
- `document.story.conflict` — valid; this represents story conflict as a document element

# Method
Build the base minimal coarse graph shape using the following process:

1. Start at the **DE**.
2. Find each notable element as a requirement.
3. Name this element's **OP** in the join which leads to it.
4. Once complete, move to the next element and treat it as the **RE**.
5. Find that element’s OPs.
6. Continue until there are no more notable elements of this artifact that must be named to understand the artifact.
7. Anneal and combine elements when the shape can logically be reduced without losing the minimal categorical understanding of the artifact.
8. Only combine elements when they can logically share a common join.
9. When combining elements, seek a common element name that can be placed in the namespace and that adheres to the namespace naming rules while logically containing the combined elements.
10. When elements are combined away into a common element, the join may contain a dictionary of the entities combined away, with each entry expressed as: the combined element, a relation in the active voice, and an observation as an atomic fact.

# Goal
Create a base shape that can be directly resolved to contain project memory graph relations and other knowledge layers that can expand this shape.

This is meant to be a shallow operation that forms a shape of notable elements which can later be extended with additional information.

It is important to realize that the goal is to establish a set of base elements as reference points that can contain regional knowledge in the project. Seeking to perform a deep intake will only hurt the project and may segment information away from the area an agent addresses as a reference. It is imperative to recognize the load-bearing nature of this statement and of this operation as a whole.

# Constraints
- Elements represent discrete functional roles actively instantiated by this artifact, named and described at their most specific reusable type level.
- Never use vague top-level labels where a specific functional mechanism exists.
- Keep all artifact-specific instance data strictly confined to the Operative Purpose.
- After working through the process, attempt to anneal joins and combine elements to a final shape that speaks to the artifact type.
- Treat the elements as elements of this artifact, joined by artifact-specific **OP**.
- Keep the graph shape minimal, coarse, shallow, and extensible.
- You must combine elements when doing so is logical and supports annealing into general specific shape.
- Where elements are combined away, the join must preserve them as a dictionary of entities using active-voice relations and atomic observations.

# Completion Condition
The task is complete when the final result is a minimal base shape of notable categorical elements of the artifact, joined by artifact-specific Operative Purposes, suitable for later expansion through project memory graph relations and other knowledge layers.
