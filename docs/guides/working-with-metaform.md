# Working with Metaform

[Documentation](../README.md) · [Getting started](getting-started.md) · [Reading the representation](reading-a-metaform.md)

Use Metaform to bring prepared understanding into a task, examine the relevant relationships, and retain what the work establishes. The examples below use the kitchen timer's map from [Getting started](getting-started.md#record-a-small-map-by-hand), registered as the project `kitchen`. For another workpiece, use the addresses returned by its own map. Join ids are generated when a join is recorded, so the examples write `<join_id>` where yours goes; `map joins` and `map where ... full=true` print them.

## Establish the current work context

```sh
metaform
metaform list projects
metaform list metaforms
metaform config --show
```

The current folder supplies context. A registered project establishes its default, and folder settings can select a different project or layer set. A project may contain multiple Metaforms; one is active.

```sh
metaform set --project kitchen
metaform activate metaform main
```

`set` persists the selection for the folder. To return to the folder's inherited/default project choice:

```sh
metaform unset --project
```

A module call can instead use `--project kitchen` for that invocation. MCP tools accept the corresponding `project` argument. Use these explicit choices when an agent starts outside the workpiece folder; do not assume that a host's folder and your terminal's folder are the same.

`metaform config` opens the settings screen; `metaform config --show --json` gives a machine-readable view. Settings are declared by the chassis and modules. A verb's switches override their values for that call. Persistent settings survive disabling a module, even though its active commands and settings rows are withdrawn.

The `modules` setting narrows the command surface for a folder. It does **not** enable or disable modules globally:

```sh
metaform set --modules map,memory
metaform unset --modules
```

Use `metaform enable <module>` and `metaform disable <module>` to change module state. The [extension guide](extending-metaform.md) explains the distinction.

## Find the functionality, then examine its relationships

Start with the represented elements rather than guessing a source directory:

```sh
metaform map roots
metaform map where code.timer.kitchen
metaform map element code.timer.kitchen
```

`roots` is the map's entry: the VE and the DE with the joins they receive, and every root element. `where` is one read of an address: the element with its address read through `name_length` and its role; `provides`, what relies on it, each join it provides with the receiver and the receiver's purpose; `receives`, what it relies on, each join it receives with the provider; the subtype joins inside those joins; the subtype join holding it, when it has one; its open work records; and what the layers in context hold at it. It leaves ids and empty fields out; `full=true` keeps them. `element` returns the element alone: its address, `name_length`, role, short name and references.

The project's own name for a functionality is on its joins, as `name`. Here the address `code.timer.kitchen` reads as kitchen timer, and the join through which it serves the cook calls it the **dish clock**.

`metaform map search <words>` finds items, memories and knowledge values, whose text holds every word. It does not search element addresses or join names, and it is not a separate semantic retrieval model.

Now look in both directions:

```sh
metaform map joins code.timer.kitchen as=receiver
metaform map joins code.timer.kitchen as=provider
```

As a receiver, an entity exposes what it needs. As a provider, it exposes whose purposes its effects serve. The kitchen timer receives the buzzer's Encounter from `code.alarm.audible` and provides the dish clock's Function to `stakeholder.cook.home`. These are different reasons to examine the same functionality.

```sh
metaform map identity code.timer.kitchen
```

`identity` is another provider-side relationship read. It is not an implementation of the exact relational type-equivalence definition in the [technical reference](../inference-metaform/REFERENCE.md#identity).

### Read a relationship as an object

For the dish clock join, the one where the timer serves the cook:

```sh
metaform map node join:<join_id>
metaform map subtypes <join_id>
metaform map where code.loop.tick
```

The join owns its purpose and has a stable ID. Its subtype joins explain contributions within that relationship: each is a join of type `subtype` held inside the purpose join, naming the element it holds, and that element stays one ordinary element record. The tick loop, `code.loop.tick`, is held only by the ticker subtype join, so it is no root and no node of the outer map; `where` at its address returns the element with its subtype join and the join holding it. `children <prefix>` traverses the namespace's type ancestry, which is a different structure from the provider/receiver joins.

Use `map links <node>` for items that link to a node, and `map citing <key> <value>` for references such as an exact source path, for example `metaform map citing path src/tick.c`. Node forms are:

```text
element:<namespace-address-or-id>
join:<join-id>
```

A subtype join is a join, named by its join id, and the element it holds is an element.

Commands with paged results return a cursor when more data remains. Pass that returned value as `after=<cursor>`; `limit=0` requests all results. `--json` supplies structured output. `--raw`, where the verb declares it, exposes stored material outside the normal current-view filtering. A raw read is an inspection operation, not a change to selected inference context.

## Retain a finding where it matters

An observation about a provider belongs at its element. A finding about why a specific receiver needs that provider belongs at the join. A note about an absorbed contribution can belong at the element it is, or at its subtype join when it concerns how it serves inside the parent's join.

```sh
metaform memory add-observations element:code.timer.kitchen "The countdown drifts one second an hour on the first board."
metaform memory add-observations join:<join_id> "The cook reads the dish name from the display, not the beep."
metaform memory open-nodes join:<join_id>
```

The first write creates the memory layer. A subsequent agent can recover the finding by the relationship's address rather than rediscovering which free-floating note concerned this receiver's purpose.

The MCP equivalent of the second write is the tool **`memory_add-observations`** with:

```json
{
  "project": "kitchen",
  "node": "join:<join_id>",
  "text": ["The cook reads the dish name from the display, not the beep."]
}
```

Tool names use an underscore between module and verb and retain hyphens **within** a verb. Thus `memory_add-observations` is the actual name, not `memory_add_observations`.

### Connect, locate, and remove memories

```sh
metaform memory create-relations element:code.timer.kitchen "rings through" element:code.alarm.audible
metaform memory search-nodes countdown
metaform memory read-graph
```

A memory relation is an item linking two nodes, with a relation label. It is not a replacement for the functional join's Receiving Entity, Operative Purpose, and Encounter Function.

The module exposes nine operations:

| Operation | What it changes or reads |
|---|---|
| `create-entities <name> <type>` | Makes a node for an address the map does not hold yet. Existing functional nodes need no entity first. |
| `create-relations <from> <relation> <to>` | Adds a linked memory item. |
| `add-observations <node> <text>...` | Adds observations at the node. |
| `delete-entities <node>...` | Deletes memory items at those nodes, **not** the underlying graph identities. |
| `delete-observations <node> <text>...` | Removes the matching observation text. |
| `delete-relations <from> <relation> <to>` | Removes matching linked memory items. |
| `read-graph` | Every memory, grouped by node. |
| `search-nodes <query>` | Nodes whose memories hold every word of the query. |
| `open-nodes <node>...` | Each node with its observations and relations. |

Memory changes in place. This build does not give memory its own revision history or provenance ledger. Its direct write path can address retained memory even when the current context masks it. The current read view still follows layer participation.

## Keep a body of knowledge as a layer

A layer identifies a question or variable and retains the values contributed in answer to it. A review might answer what was established about the timer's behavior; a practice layer might carry general engineering knowledge; an imperative layer might carry selected instructions for an operation. These purposes are not interchangeable.

Create a review layer and add a local finding:

```sh
metaform map knowledge op=create layer=review-notes variable="What this review established." mutable=true hideable=true
metaform map knowledge op=add-item layer=review-notes node=element:code.timer.kitchen value='{"finding":"Each dish keeps its own countdown."}'
metaform map knowledge op=finish layer=review-notes
```

These shell examples use POSIX-style single quoting around JSON. The tool equivalent supplies the JSON value as structured data rather than a shell string. For example, `map_knowledge` accepts `op`, `layer`, `node`, `value`, and `project` as named arguments.

The layer starts **building**. Finishing makes it available to normal selection. The returned layer name is authoritative: a name already used by a different declaration can result in a numbered name and notice. Read operation results rather than assuming every requested name was installed unchanged.

`map knowledge` writes one object per call: `op=add-element` takes an element's `address`, `name_length`, `role`, `refs` and `extra`; `op=add-join` takes the receiver, the provider, `name`, `purpose`, `function`, `ef`, `relation`, `verb`, `observation`, `non_goal`, `type`, `refs` and `extra`; `op=add-subtype` takes the parent `join`, the `address` of the element it holds and the subtype join's fields. Nothing is refused for its content: a field that is missing is stored empty and named in a notice, and a call stops only when it lacks a field its record cannot be stored without, such as a join's receiver, BASE-038.

```sh
metaform map layers
metaform map layer review-notes
metaform map node element:code.timer.kitchen
```

`layer` reads the named layer directly. `node` groups participating items by layer at that node. A node-local item does not become inherited knowledge merely because its address has ancestors.

### Place general knowledge at its applicable type

A **property** is the store's branch-scoped knowledge mechanism. Unlike a local item, it travels the namespace. For an illustrative informational property:

```sh
metaform map knowledge op=add-property layer=review-notes element=type:code value='{"information":"The firmware is C for one microcontroller."}'
metaform map context code.timer.kitchen
```

This is a demonstration of placement, not an added rule that every task must follow. The `type:` form targets a namespace prefix: when no element holds that address, the layer records one there to hold the property and says so in a notice. A property at `code` applies to its descendants. Properties attached toward the leaves from the current scope can be **visible** from an ancestor without thereby applying to every sibling branch. The context result separates `applying` and `visible`.

Properties implement scoped context support; they are not, by themselves, a producer that derives every semantic consequence of an Encounter. [Encounter propagation](../inference-metaform/REFERENCE.md#encounters) explains the full mechanism and [the implementation map](../inference-metaform/IMPLEMENTATION_MAP.md#selection) locates its current support.

When creating a layer derived from other layers, the `sources` JSON array records those source layer names or IDs. Optional provenance fields include `module`, `workflow`, `prompt`, `model`, `role`, and `blinded`. Record the actual inputs and execution identity; the store does not discover all derivation links automatically.

## Select the understanding for a task

Without a nonempty explicit layer selection, the ordinary starting set includes all finished, nonhidden, non-correction layers. Local settings then remove or add participation along namespace prefixes. A local mask defaults to preserving incoming membership; a local select defaults to adding nothing. This is not a default-deny scheme.

For example, exclude review notes from the `code.timer` branch, then restore them for the kitchen timer:

```sh
metaform map mask code.timer review-notes
metaform map select code.timer.kitchen review-notes
```

The selection toward the leaves does not turn those notes on for siblings. Remove these local choices with:

```sh
metaform map clear code.timer.kitchen review-notes select
metaform map clear code.timer review-notes mask
```

At each prefix, the effect is **incoming membership, minus local masks, plus local selections**. The full resolver, including an explicitly empty API starting set, is documented in [the reference](../inference-metaform/REFERENCE.md#layers).

For a folder-wide explicit starting selection, use names or tags through `metaform set --layers <comma-separated-values>`; `metaform unset --layers` restores the default. Choosing only a new review layer can omit the intake layer from normal context. Include the intended intake layer when that is part of the context you want, rather than assuming an always-on structural core.

### Hide is not delete

```sh
metaform map hide review-notes --confirm
metaform map unhide review-notes
```

Only hideable layers can be hidden. The store also excludes derived layers whose explicitly recorded sources depend transitively on hidden layers. It does not infer unlimited semantic invalidation from any association. Direct reads of the retained layer remain distinct from its participation in normal context.

Intake, knowledge, memory, and corrections have different lifecycles. In particular, corrections are not selectable/hideable knowledge overlays; they apply through the correction stack.

## Record the condition of an object as work

The map holds the intended functional shape. The condition of an element or a join, a subtype join included, is a work record, kept apart from the map: `tbd`, to be done or determined, `broken`, or `cruft`, with a note saying what and where and a task saying what it needs. Writing or changing one never changes the map and is never a correction.

```sh
metaform map work op=add node=element:code.alarm.audible condition=broken note="The alarm pin is unconnected on the second board revision." task="Wire the alarm pin on revision two."
metaform map work node=element:code.alarm.audible
metaform map work op=done id=<work_id> resolution="Wired on revision two."
```

`op=add` returns the record's `work_id`; `op=edit` changes its condition, note, task, `held` or `reviewed`; `op=done` marks it done with its resolution kept beside it. `op=take` says an agent has started on the task: a `tbd` record becomes `in-progress` and a `broken` one `fixing`, and a record taken or done cannot be taken again, so two agents never hold one task. On the map a part waiting to be built is drawn in characters, and they change faster while an agent works on it. With no `op`, `map work` lists records, by `node`, `condition` and `open=true` or `false`. Every element and join read carries `open_work`, the conditions of its open records, and `where` lists them. The intake agent writes these as it maps, a critic with its findings, and any agent at any time.

## Correct represented understanding

Use a correction layer when changing the established representation while retaining the change and its reason. Ordinary mutable notes are not a substitute for that history.

The command shape is:

```text
metaform map knowledge op=create layer=clarification variable="What this correction changes." kind=correction mutable=false hideable=false
metaform map knowledge op=correct layer=clarification id=<record-id> observation="<corrected observation>" reason="<why it changes>" evidence="<supporting evidence>"
metaform map knowledge op=finish layer=clarification
metaform map history <record-id>
metaform map stack
```

Replace the angle-bracket fields with the actual target and reasoning. A correction begins in the building state and is applied on finish. `op=peel layer=<top-correction>` takes the top correction off the stack and returns it to building. Use the stack order shown by the store; this is not arbitrary undo of an interior layer.

An element cannot be moved: its address is its identity, and another address is a different element. An `address` given to `op=edit` or `op=correct` for an element is not applied, and the notice says to record the element at the new address and move its joins. A join can be moved: `receiver` or `provider` moves it, and `parent=<join_id>` makes it a subtype join inside that join, keeping its purpose. A moved join keeps its id and everything attached to it. An element recorded again at an address it held before is the same element, with its memory, items and joins.

Corrections can mark dependent knowledge as requiring re-examination. After examining the affected knowledge, `metaform map reexamined <layer>` records that state. Neither finishing a correction nor marking a layer re-examined automatically performs the reasoning.

`op=edit` and `op=correct` do not read `ef` or `verb`: a value given for either is named in a notice and ignored, so a join's Function or Encounter word cannot be changed through `map knowledge`. `intake edit` changes both while an intake is building, and the Python store's `edit` and `correct` take them. [Correspondence issue C01](../inference-metaform/IMPLEMENTATION_MAP.md#c01) identifies the exact omission.

## Use prompting and criticism without changing the assignment

Project-grounded lexicalization first resolves a request's generalized referents to recorded project names and functional addresses. It replaces the corresponding terms while retaining the requested operation, then provides mappings and knowledge directions. It stops before execution. The [walkthrough](../examples/project-walkthrough.md#4-lexicalization-before-execution) shows the transformation and the recorded names supporting it.

There is no shipped lexicalization verb in this edition. The present name, graph, context, memory, and prompt-version facilities are available to an agent or module implementing that operation. Existing prompts can be listed and inspected with `metaform prompts` and `metaform prompt <name> [version-number]`; the GUI can save new versions of existing prompts. Prompt storage is not itself the lexicalizer.

Selected memory may be **information** to reason from, or **additional imperatives** when its layer has that purpose. An informational observation does not silently rewrite the task. Explicitly selected imperative knowledge can supply instructions and acceptance criteria separately from the lexicalized request.

### Respond substantively to a blindspot challenge

A blindspot challenge presents a gap in the design: a function or Encounter the system should have and appears not to. The critic finds it by examining the Metaform alone, or the actual source and Metaform together. The project response establishes one of three substantive outcomes:

**A:** The concern was considered and adds no benefit, with the reasoning why. **B:** It was not considered and has relevant consequences to explore. **C:** Another part of the system already handles it, identifying the location and functional relationship.

The implemented state operation is:

```text
metaform map answer <challenge-item-id> A
metaform map answer <challenge-item-id> B
metaform map answer <challenge-item-id> C link=<location-or-reference>
```

These are alternatives, not a three-command sequence. `answer` stores the state, optional link, and time; it has no rationale field. Retain the reasoning in the appropriate item or layer as well. The current state operation does not automatically compose that rationale, perform the critique, or join all of the exchange into an autonomous producer.

`metaform map approve <challenge-item-id>` is the existing CLI-only approval operation for a B challenge. Direct plan creation is a separate supported operation and does not acquire an invented approval prerequisite from this path. The [technical reference](../inference-metaform/REFERENCE.md#criticism) explains the reasoning exchange; the [implementation map](../inference-metaform/IMPLEMENTATION_MAP.md#challenges) explains the state and plan facilities.

## Using the web interface

```sh
metaform web
metaform web stop
```

The first command starts or locates the shared web process for the current Metaform home and prints its address. The second stops it. The default bind is loopback at port 7433. The source has separate host/origin and token handling for a non-loopback bind; do not treat changing `web_bind` as equivalent to the default local-only exposure.

The header holds the project and Metaform selectors, **Clear project**, and a **Layers** button that counts the layers shown, such as `Layers · 3 of 5`, and opens a checklist with one row per layer and **Apply to folder** at its foot. The left pane holds the two-dimensional map, with **Back**, **Forward**, the breadcrumb and **Fit** on a strip above it, and four inspection tabs: **Object**, **Provenance**, **Prompt**, and **Corrections**. The three-dimensional graph fills the right, and every item of the layers turned on is its own node there. Select a graph object to inspect its recorded content. In the 2D view, use Fit or `F`; the 3D view supports orbit, zoom, selection, and layout controls.

The checklist selects what the view presents. **Apply to folder** persists the chosen layer context for that folder. A temporary visual selection and the folder's working context are different operations.

The page shows each node's condition from its work records: a node with an open `tbd` record is drawn at 70% opacity and turns solid once its task is done, one with an open `broken` record flashes red, and `cruft` keeps its look. The Object panel lists the selected object's records with their note, task, held and reviewed flags, and the resolution once done.

The page follows the map without polling. After any command that changes a project's map, on the command line or over MCP, and after the page's own writes, `map.changed` is announced and the server pushes it to every open page, which redraws without a reload. An intake being recorded is drawn as each object arrives.

The Prompt tab exposes existing prompt versions, comparisons, and **Save as new version**. It does not generate a lexicalized prompt merely because it displays prompt records. The Corrections tab presents the relevant retained changes rather than editing the runtime source.

**Clear project** in the header does what `metaform clear project <project> --confirm` does for the selected project: it removes the project's metaforms and report files and keeps its registration, folder, settings, origins and variants. It first shows the command's own caution and asks on the page. Afterwards every open page shows the project with no metaform until the next intake.

## Retain and exchange the work

Write the map as a short Markdown document, to read or to pass on:

```text
metaform map markdown file=kitchen-map.md
metaform map markdown address=code.timer.kitchen
```

It holds each element's name, address, role and paths, and each join's receiver, provider, relation, purpose and non_goal. With an address it covers that element and what stands around it. The web GUI's Export button saves the same document.

Export the current project to a file:

```sh
metaform export file=kitchen-export.json
```

Narrow the export by Metaform or layer when useful:

```text
metaform export kitchen file=main-export.json metaform=main
metaform export kitchen file=layer-export.json layer=<layer-name>
```

With no `file=` the document goes to standard output. Import into a registered project with:

```sh
metaform import kitchen-export.json kitchen
```

Exchange preserves IDs and adds missing records. It does not overwrite an existing identity with a later copy of the same ID. A Metaform already owned by another project in the same home is not duplicated into a second owner; the import reports that condition. A document written at another schema version is refused with the version it has and the one this Metaform supports. This is exchange of retained representation, not Canonical Intake recording.

Direct-wheel work can be pulled into the normal home with `metaform import wheel=metaform-0.1.0`. Pulled Metaforms receive distinguishable names and are not made active automatically.

### Keep artifact variants as well as the map

The history facilities retain the artifact's realization separately from its inferred representation:

```sh
metaform add origin
metaform list origins
```

After work in a folder, a variant can be captured against a chosen origin:

```text
metaform add variant <work-folder> origin=<origin-id>
metaform list variants origin=<origin-id>
metaform extract <variant-id> <empty-destination-folder> origin=<origin-id>
```

An origin is based on the repository commit or a plain-folder copy. Variants record differences against an origin; extraction reconstructs and verifies the resulting content. The destination must be empty for extraction. The optional `remove=true` variant behavior is not needed for ordinary capture and is not used here.

Artifact variants, layer provenance, correction history, and prompt versions are distinct records. They become a connected account of a task when the actual associations are recorded; the presence of each facility is not proof that every producer automatically records every association.

## Reports and further reading

```sh
metaform list reports
metaform read report <file-name>
metaform feedback "<observation about the process>"
```

Report records can be associated with projects and layers. `feedback` also accepts report and partial-shape material; use `metaform help feedback` for its exact text/file/stdin forms.

For interpretation rather than command execution, continue with [Reading an Inference Metaform](reading-a-metaform.md). For a capability that should become a reusable module, use [Extending Metaform](extending-metaform.md). The [implementation map](../inference-metaform/IMPLEMENTATION_MAP.md) is the source-level companion to this guide.
