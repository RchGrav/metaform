# Metaform: the design, end to end

**Status:** Written by an agent on 2026-11-11 from the owner's explanations, the owner's documents and the code. It is an interpretation in the agent's words. The owner corrects it; where the owner and this document differ, the owner is right and this document is wrong. Section 12 lists where the build differs from this design today.

**How to read it:** each part says what the thing is, then why it is that way. The reasons are part of the design. A builder who follows the rules without the reasons will rebuild the mistakes listed in section 12.

## 1. What Metaform is for

An agent that enters a project must first work out what the project is. It reads files, follows references and builds a picture. That work draws on the same limited capacity the agent needs for the task it was given. A large project can consume most of that capacity before any useful work starts.

Metaform does that orientation once and keeps the result. The result is a small map of what the project does: its functional parts and what each part relies on. An agent reads the map in one pass and knows what the project is.

The saving is in reasoning. It is not measured in tokens or money, and Metaform does not make a model more capable. It keeps the model's capacity free for the task.

The map has a second job. Because every part has an address, the map is the place where knowledge about the project is kept: sources, written specification, memories, work in progress. Knowledge attaches to the part it concerns, so an agent that works on one part receives what applies to that part and nothing else.

The map also has a third job, which the rest of the owner's work builds on. A map says what an artifact is and what must stay true for it to remain that kind of thing. That is the footing needed to evaluate an artifact from the side of each party it serves, and to change it under rules without turning it into something else. This applies to any artifact: software, a photograph, a story, a contract.

## 2. Three ideas the rest depends on

**The map describes functionality, not the artifact's material.** For software it does not list files, functions or types. It names what the software does. Two programs in different languages that do the same things have the same shape. The same holds outside software: a photograph's map names what the photograph presents and how its parts serve that, not its file format.

**The map is an inference, not a measurement.** No correct map exists to compare against. Two models produce two readings, and both are valid. The map's value starts after it exists: it becomes the shared frame that later agents reason from. So a map is never graded, and the procedure that makes it is never gated. What matters is that a map can be inferred, that it holds together, and that it is light enough to take in at once.

**The address is general and the record is specific.** An address names a type of functionality that could exist in many projects. What this project does with it is written in the records at that address. This keeps the shape stable and comparable, and it keeps the particulars where they can change without moving anything.

## 3. Vocabulary

The intake procedure has its own coined terms. They are slightly open in meaning on purpose: each one settles its meaning from the artifact in front of the model, which is how one procedure serves a router and a photograph alike. The procedure text is the owner's and is not restated here. This section gives the working meaning of each term so the rest of the document can be read.

| Term | Working meaning |
|---|---|
| Artifact | The thing being examined, made or changed. |
| Element | A functional part of the artifact, named as a type. Being nameable does not make a part worth an element. |
| Address | The dotted name of an element. Read in reverse, with spaces, it is the element's ordinary name. |
| Defining element | The one element without which the artifact is no longer the same kind of thing. |
| Supportive element | An element bound to the defining element so closely that removing it also changes what the artifact is. |
| Notable element | An element that states a demand: something the artifact needs from, or owes to, what is outside it. |
| Divergent element | An element found during intake that does not fit. It is investigated, then repaired or removed. |
| Parametric | A quality or quantity that can be tuned but has no name of its own in artifacts of this type. It is never an element. |
| Receiving element | The element that has a purpose for another element. |
| Providing element | The element that satisfies that purpose. |
| Operative Purpose | What the receiving element is trying to accomplish through the providing element. |
| Encounter Function | What the providing element does in that meeting that satisfies the purpose. |
| Dependency | The record a receiving element keeps about one providing element. Section 5. |
| Overlay | A named kind of knowledge laid over the map. Section 8. |
| Mask | A stop that keeps an overlay from showing at one element and beneath it. Section 8. |

Two names changed on 2026-11-11 by the owner's decision. The dependency was called `wants`, and before that a join. An overlay was called a layer.

## 4. The base shape

The base shape is the set of elements and their dependencies. It holds functionality and nothing else.

### 4.1 Addresses

- An address is a path of segments separated by periods, from the general to the specific.
- Every prefix of an address is itself a complete type. A child is the same kind of thing as its parent, or a function within it.
- Reversing the segments gives a name a practitioner recognises. `code.engine.game` reads as "game engine".
- A segment names a functional approach. It never names a language, an encoding, a medium, a genre, a style or a particular product. Those are variants of functionality, and an address built on a variant splits knowledge that belongs together.
- Terms are the established ones for that class of artifact. No term is coined for an address.
- The namespace has no fixed depth and no filler segments.

**Roots.** Four roots hold what is inside the artifact: `code`, `document`, `media`, `data`. Two prefixes hold what is outside it: `upstream` for what the artifact relies on, `downstream` for the parties that rely on it. One root, `overlay`, is internal to Metaform and holds overlay definitions (section 8). An intake never writes there.

### 4.2 An element

| Field | Holds |
|---|---|
| `technical_name` | The ordinary name read from the address, as many leading words of the reversed address as make a recognised term. |
| `name` | The project's own name for this functionality. When the project has none, the ordinary term. |
| `role` | Defining, Supportive, Notable or Divergent. One element in a map is Defining. |
| `uri` | One reference to where this functionality starts in the artifact. |
| `status` | Present only when the functionality is intended and not built. |
| `dependencies` | Section 5. |

An outside party under `downstream` is an element too. Each one that matters is a type of party whose own purpose drives change in the artifact. The person who asked for the intake, "the user" and "the developer" are not such parties: they could be named for any artifact, so naming them says nothing about this one.

### 4.3 What the shape leaves out, and why

The shape is shallow and coarse on purpose. Its elements are reference points that knowledge attaches to.

A deep shape harms the project. Each added element moves some knowledge away from the place an agent will look for it, and makes the shape slower to take in. So the procedure combines elements whenever one element's records can carry the detail of another. A part that was combined away is not lost: its address is kept as an inactive subtype, where knowledge may still be attached later.

Detail lives in the records and in overlays. Settings, counts, file lists and identifiers from the code are never elements.

## 5. Dependencies

A dependency is the record one element keeps about another element it relies on.

| Part | Holds |
|---|---|
| The key | The address of the element relied on. The address is the dependency. |
| Purpose | The Operative Purpose: what the holder is trying to accomplish through it. |
| Function | The Encounter Function: what the other element does, in this meeting, that satisfies the purpose. |
| Direction | Which way the substance moves, seen from the holder: inbound, outbound or two-way. |

**The holder owns the record.** The same providing element can serve several holders through different functions, so the function cannot be stored once on the provider. It belongs to the meeting, and the meeting is recorded by the side that has the need.

**Direction is about substance.** A request, a parameter or a receipt is not the direction. An element that asks for a value and gets it back has an inbound dependency. An element that hands a record to a log has an outbound one.

**Every dependency traces back to an outside party.** An outside party has a purpose for the defining element. The defining element has purposes for other elements, and so on. An element that nothing has a purpose for is an orphan, and the tool can list orphans.

**The record is more than a line between two boxes.** The structure was first conceived as a hypergraph whose relations are things in their own right and can hold logic. A dependency keeps that property: knowledge can attach to it, and the parts combined away during intake are remembered in it.

**Stored names.** The owner's design keeps the intake's concepts in the procedure and gives the stored fields plain names, `why` for the purpose and `how` for the function. The reason is that agents who read the map later should not need to learn the intake's terms. The procedure tells the intake agent which concept goes in which field.

**Wording.** A purpose is written so that it completes "…in order to", and a function so that it completes "…, which". Both are fragments in plain technical English, without settings or values. The reason is composition: stored fragments are later placed into rendered sentences and instructions, and no code should have to conjugate or repair them. This is a contract for the writer, not a test applied to the result.

## 6. Intake

Intake is the procedure that infers the base shape from an artifact.

- **It is the owner's text.** The procedure is held in the repository byte for byte as the owner wrote it. Nothing in the system rewords it, renames its terms or adds rules to it. Tooling is made to fit the procedure, never the reverse.
- **The server delivers it.** An agent asks the tool for the intake procedure and receives it, with the person's prompt bound in. An agent does not receive it at connect, and no agent or person has to paste it in. Section 9.
- **It is never gated or judged.** The tool checks that a command has a valid shape. It does not judge what an agent inferred. Refusing a purpose because of its wording replaces the model's reading with a rule, and the reading is the product.
- **It records as it reasons.** One element or one dependency per command, at the moment it is inferred.
- **It ends with a proof.** The agent reads the whole map back, compares it with the artifact, corrects it, combines what can be combined, and stops.

A prompt can also ask for something other than a first intake: a look for blind spots, a correction, or new functionality. The procedure covers these as variations of the same operation.

## 7. After intake

A finished map is not inferred again when the project changes. A second inference would give a different reading and remove the frame agents have been working from.

The map grows instead. New functionality is placed into the existing shape: which element has a purpose for it, what it provides, where it sits in the namespace. Functionality that is intended and not built is recorded with that status, so the map can hold a design before any of it exists. This is how one mechanism serves an existing project and a new one.

Earlier versions of an element are kept. Agents have been orienting by them.

## 8. Overlays

An overlay is a named kind of knowledge laid over the base shape. The base shape does not change when an overlay is added or removed.

- **Definition.** An overlay exists once it is defined at `overlay.<name>`. The definition record is the overlay's schema: it says what a record of this overlay holds, how each part is worded, and how records are rendered as sentences. A new overlay needs no code.
- **Unlimited.** A project can define any number of overlays. For that reason an overlay's schema is never part of the tool's definition. It is read from the map, at the overlay's own address, when an agent goes to write that overlay.
- **Records.** An element holds an overlay's records in a list under the overlay's name.
- **Placed.** An overlay is placed at an element by naming it in that element's `overlays`. It then applies at that element and at everything beneath it.
- **Masked.** An element masks an overlay by naming it in `masked_overlays`. The overlay stops there and does not reach beneath. Masking hides and does not delete. To remove an overlay from one small region, mask that region.
- **The project's list.** The project lists the overlays that are on. An overlay that is not listed is off everywhere, with its placements and records left as they are.
- **Active** is the result of those three things at one element. It is a word for the outcome and not a stored value.

Overlays are how work is scoped. A port from one language to another adds an overlay for the old code and one for the port, places them where the work is, and removes them when the work is done. The base shape was the same before, during and after.

Three overlays come with the system: sources, skills and memory. The written specification is an overlay too, and the tool can render it as a Markdown document and take an edited document back.

## 9. The tool

Agents reach the map through one tool with a short list of operations.

### 9.1 The rule: progressive discovery

No information is presented before it is needed, and nothing is presented that is not needed. Every answer the tool gives is held to that test.

- The tool's whole definition is under one kilobyte. It names the operations and says no more.
- An agent that connects and never writes pays for nothing else.
- The shape of a command is learned when the agent goes to send one, in one of two ways: it asks, or it gets it wrong and is corrected.

### 9.2 Operations

| Operation | Does |
|---|---|
| `map` | Returns the shape alone: addresses and which relies on which, and the defining element. |
| `goto` | Places the agent at an address and returns what is linked there. A later visit in the same context returns only what changed. |
| a bare address | Reads one element. |
| a key starting with a period | Returns the stored form beneath that path. |
| `orphaned` | Lists elements nothing relies on. |
| `add`, `update`, `delete` | Write. An element is written in the same form it is stored in. |
| `help` | With nothing, returns the form of help itself, which lists what can be asked. With a name, returns the form of that one thing and names what can be asked next. One level per answer. |
| `intake` | Returns the intake procedure for a prompt. |

### 9.3 Validation is the teacher

A command with a wrong shape is refused. The refusal repeats the command, says in a short sentence what is wrong, and hands back the command that would be accepted. The agent sends that.

This is why the definition can be small. The tool does not describe every shape to every agent in advance. It gives one agent the one shape it needs, at the moment it needs it.

Three properties follow:

- A correction never removes or alters anything the refused command did not address.
- A refusal is about shape and integrity only: an unknown field, a missing part, a delete that would leave a dangling dependency. It is never about meaning.
- Every refusal the tool can give hands back a usable command. A refusal with no correction is a defect.

### 9.4 Writes carry intent

A write creates the path it needs. An agent says what it means and the tool does the work behind it. A delete that would break a dependency is refused, with the command that removes the dependency first.

## 10. Storage and the three forms

Metaform ships in Rust, Node and Python. The three are the same tool.

- **Facing the agent:** nested elements, each with its fields together, in the form an agent reads and writes.
- **In the database:** one narrow table or column per field and per overlay, keyed by element. A read of one field touches one column. An overlay that is off costs nothing to skip.
- **One owner per home.** One process owns a home's stores. Every other process goes through it. Each command is one transaction.
- **Identical behaviour.** A shared suite sends the same commands to all three forms and compares every answer byte for byte. A difference is a defect in whichever form differs from the design.

## 11. The interface

The interface is designed and written from scratch. It takes no code from the two earlier pages. Section 11.14 says how it is judged against them.

### 11.1 What it must do

A person opens it and sees what the project is. They move through it without losing their place. They read any part in plain words. Nothing on screen moves unless they caused it.

Three promises govern every decision below:

1. **Text is always legible.**
2. **The person always knows where they are and how to get back.**
3. **Motion always has a cause the person can name.**

### 11.2 Legibility is a floor

Text is never drawn smaller than 12 CSS pixels. Zooming out does not shrink text; it reduces how much is shown.

- The first view shows as many levels as fit with every name at or above the floor and no two names overlapping. Deeper levels are folded into their parents, each with a count of what it holds.
- A name sits inside its element while the element is large enough to hold it. When the element is drawn smaller than its name, the name leaves the box and is placed in the nearest free space beside it, joined by a short line.
- Names are placed in priority order: the selected element, the elements it shares a dependency with, the defining element, then by how many elements rely on each. A name that cannot be placed without overlap is not drawn, and its element shows a mark that it has one.
- No name is cut short on the map. A long name wraps to two lines before it is shortened anywhere.

### 11.3 Three bands of detail

What an element shows depends on how large it is on screen, not on a mode.

| Band | Element is | Shows |
|---|---|---|
| Overview | under 28 px tall | A mark in its role's shape, with names floated beside the most relied-on elements. |
| Map | 28 to 72 px | A box with the name and the role mark. |
| Close | over 72 px | Name, technical name, role, overlay marks, and counts of what it relies on and what relies on it. |

A band change cross-fades over 140 ms. The thresholds have a margin of 15 percent each way, so an element at a boundary does not flicker.

### 11.4 One camera, one law of motion

All movement of the view is the movement of one camera, and it follows one law.

- **A flight** from one view to another moves position and zoom together along the path that keeps the eye oriented: out, across, in. A short move does not zoom out at all.
- **Duration** follows distance: 220 ms for the smallest move, up to 900 ms for the longest, eased at both ends.
- **Interruptible.** A new destination during a flight starts from the camera's current position and speed. Nothing snaps.
- **The hand always wins.** Any touch of the wheel, a drag or a key stops a flight at once and gives the person the camera.
- **Wheel** zooms toward the pointer and coasts for 180 ms. **Drag** pans and coasts for 400 ms after release. Both coast to a stop; neither bounces.

The camera moves for five reasons only: a gesture, a dive, a step back, a fit, and bringing an off-screen selection just into view. It never moves because the map changed.

### 11.5 Navigation has six verbs

| Verb | Gesture | Effect |
|---|---|---|
| Select | Click, or arrow keys along dependencies | Marks the element and fills the panel. The camera stays. |
| Dive | Double-click, or Enter | Flies to frame the element with what it relies on and what relies on it. Everything else fades to a quarter strength and stays in place. |
| Back | Escape, Backspace, or the Back control | Returns to the exact view and selection before the last dive. |
| Home | H, or the Home control | The whole project, as first shown. |
| Unfold and fold | Click the count on an element | Shows or hides what the element holds. |
| Find | / then type | Flies to the element found and selects it. |

The Back control is always visible, always in the same place, and says where it leads. A trail beside it shows the path of dives, and each step in it is a way back. No gesture changes meaning between views.

### 11.6 Layout

- The shape is laid out in ranks by dependency. The parties the project serves are at one end and what it relies on outside is at the other.
- The layout of the whole shape is computed once and kept. Folding and unfolding do not lay out the world again. A folded branch draws into its parent; the parent keeps its place; neighbours close the gap along their own rank.
- A dependency is drawn as straight runs with right-angle turns and rounded corners. Parallel dependencies run side by side in their own lanes. The arrowhead is at the end where the substance arrives.
- Elements under `upstream` and `downstream` are drawn in a distinct outline, so the edge of the project is visible without a frame around it.

### 11.7 Transitions

One small set of motions is used everywhere.

| Motion | Form | Time |
|---|---|---|
| Appear | Grows from its parent's place, from 30 percent size, fading in | 320 ms |
| Leave | Fades where it stands | 180 ms |
| Move | Slides to its new place, fast then slow | 420 ms |
| Lines | Redrawn after elements land, fading in | 160 ms |
| Levels | Each level starts 24 ms after the one before | at most five levels |

No change takes longer than 700 ms in total. When the person has asked the system for reduced motion, every change is immediate and the changed elements are outlined for one second.

### 11.8 Flow

Movement on the lines shows what direction means, and it is shown only for the selected element's dependencies.

- For an inbound dependency a small mark travels from the holder to the provider, and the substance travels back. For an outbound one the substance travels out. For two-way, both.
- Timing and size vary from one cycle to the next so that no two lines move in step.
- Nothing animates when nothing is selected. At rest the page performs no drawing at all.

### 11.9 The panel

One panel, in one place, reads top to bottom:

1. What the element is: its name, its ordinary name, and its role with one sentence that says what the role means.
2. What relies on it, and what it relies on. Each dependency is written as a sentence: this relies on that in order to do something, which does something. The direction is shown beside it.
3. Its overlays, each with its records.
4. Where it starts in the artifact.

Each line that names an element selects it. Editing happens in place: the edit is sent as a command, and a refusal is shown with its reason and its correction.

### 11.10 Overlays and live change

- A list shows each overlay with whether it is on for the project. Selecting one marks the elements where it is placed and where it is masked, and one further control keeps only those elements at full strength.
- When an agent changes the map, the changed elements carry a mark until looked at, and a count at the edge of the view says how many are off screen. The count is a control that flies to them.

### 11.11 Budget

- No WebGL and no shaders. Drawing is two-dimensional, and animation moves and fades what is already drawn.
- Sixty frames a second with 300 elements in view on integrated graphics.
- First view of a 200-element map in under half a second after the data arrives.
- No work at rest.

### 11.12 Access

Dark first, with a light theme. Contrast meets the AA level. Every state is shown by shape or words as well as colour. Every action has a key, and focus is always visible.

### 11.13 Scope

The interface shows one project at a time and lists the others. It reads through the host that fronts the tool, follows changes as they are announced, and writes through the same commands an agent sends. Proposals from an agent, the Markdown document and the activity list are panels of the same interface and are built after the map passes 11.14.

### 11.14 How it is judged

The interface is accepted when all of these hold on the Flask map and on a map of at least 250 elements:

| Measure | Target |
|---|---|
| Smallest text on screen in any view | 12 px or more |
| Overlapping names | none |
| Names cut short on the map | none |
| Time for any transition | 700 ms or less |
| Frame time during a flight | 16.7 ms or less at the 95th percentile |
| Drawing at rest | none |
| A person who has never seen it answers: what is this project, who is it for, what does part X rely on and why, which part is not built | all four, without help |
| The same person dives three levels and returns to the first view | no wrong turn |

It is improved by a fixed loop: choose one thing, alter that one thing, measure the same list, keep the change only if a measure improves and none worsens, and record the result with a picture.

## 12. Where the build differs today

| Design | Build on 2026-11-11 |
|---|---|
| The intake procedure is the owner's text, unaltered (6) | The repository's procedure is a rewrite that removed the intake's concepts and merged the tool's commands into it. |
| The server delivers the intake procedure (6, 9.2) | The server delivers no procedure. An agent has it only if someone pastes it in. |
| The record is a dependency, and knowledge is an overlay (3) | The stored names are still `wants`, `layer`, `layers` and `blocked_layers`. |
| An overlay's definition is its schema (8) | A definition holds a description and an instruction. The checks for the one built overlay are in the code. |
| Placement, masks and the project's list decide where an overlay is active (8) | Not built. |
| Every refusal hands back a usable command (9.3) | Two known refusals do not. |
| Answers hold nothing unneeded (9.1) | `goto` returns empty counts; `map` lists parent addresses with elements; `orphaned` returns whole elements. |
| Earlier versions of an element are kept (7) | Not built. |
| The interface of section 11 | Not built. Two earlier pages exist and neither meets it. |
| The tool's definition is under one kilobyte, with `help` one level at a time (9) | Built: 672 bytes. |
| Three identical forms with a column-per-field store (10) | Built and compared on every command of the shared suite. |

## 13. How each part is verified

- **The tool:** the shared suite, with every answer compared across the three forms; a check that each refusal's correction is accepted when sent; the size of the tool's definition and of each `help` answer held as fixed numbers.
- **Delivery:** a recording of everything one agent receives during an intake, read against the rule of 9.1: for each piece, was it needed, and was it needed yet.
- **Intake:** not graded. The owner runs the procedure across models and artifact types and reads the results. The tool's part is only that the procedure arrived unaltered and that nothing was refused for its meaning.
- **The interface:** the list in 11.14.

## 14. Decisions that are the owner's

1. **Which procedure text governs.** The design needs one text named as the intake procedure. Candidates exist in several versions; this document does not choose.
2. **Whether `why` and `how` hold.** The owner's design has not been run: concepts intact, fields plainly named. One run each way on the same artifact and model settles it.
3. **Where the remaining parts of the first design's record live.** The early procedure's record also held a relation, an observation true of all artifacts of the type, and the parts combined away. They belong either in the dependency or in an overlay.
4. **Whether an outside party has a role.**
5. **The name of the internal root** (`overlay` is assumed here) and whether "placed" is the right word for naming an overlay at an element.
