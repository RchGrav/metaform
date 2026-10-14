# Working with Metaform

[Documentation](../README.md) · [Getting started](getting-started.md) · [Reading the representation](reading-a-metaform.md)

Use Metaform to bring prepared understanding into a task, examine the relevant relationships, and retain what the work establishes. The examples below use the kitchen timer's map from [Getting started](getting-started.md#record-a-small-map-by-hand), registered as the project `kitchen`. For another workpiece, use the addresses returned by its own map. Ids are generated when a thing is recorded, so the examples write `<join_id>` and `<id>` where yours goes; `map joins` and `map where ... full=true` print them. Map reads name elements by address and joins by their receiver and an element they hold. The intake uses the same addresses and calls those records purposes.

## Establish the current work context

```sh
metaform
metaform list projects
metaform list bases
metaform config --show
```

The current folder supplies context. A registered project establishes its default, and folder settings can select a different project or layer set. A project may hold several bases, each a map with a store of its own; one is active.

```sh
metaform set --project kitchen
metaform activate base main
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

An alias gives two or more modules one name at the top menu. `metaform <name>` then lists the commands of each module it stands for, and they run by their module's name. It holds in the folder it is defined for and every folder below it; `folder=<path>` defines it for a worker's folder:

```sh
metaform alias mapping map memory
metaform mapping
metaform alias mapping map memory folder=~/wt/job1
```

## Find the functionality, then examine its relationships

Start with the represented elements rather than guessing a source directory:

```sh
metaform map roots
metaform map where code.timer.kitchen
metaform map element code.timer.kitchen
```

`roots` is the map's entry: the CQU and the DE with the joins they receive, and every root element. `where` is one read of an address: the element with its address read through `name_length`, its role and its `name`; `provides`, what relies on it, each join that holds it with the receiver, the receiver's purpose, the join's `ef` and `ifd`, and the elements the join holds; `receives`, what it relies on, each join it holds as receiver with the elements that serve it; its open work records; and `layers`, what the layers in context hold at it, the `sources` layer's refs among them. It leaves ids and empty fields out; `full=true` keeps them. `element` returns the element alone: its address, `name_length`, role, short name and `name`.

The project's own name for a functionality is on its element, as `name`. Here the address `code.timer.kitchen` reads as kitchen timer, and the project calls it the **dish clock**.

`metaform map search <words>` finds items, memories and knowledge values, whose text holds every word. It does not search element addresses or names, and it is not a separate semantic retrieval model.

Now look in both directions:

```sh
metaform map joins code.timer.kitchen as=receiver
metaform map joins code.timer.kitchen as=provider
```

As a receiver, an element exposes what it needs: the joins it holds, each with the elements that serve it. As a provider, it exposes whose purposes it serves: the joins that hold it, each with its receiver. The kitchen timer receives from `code.alarm.audible` the sounding of the end of a countdown, and serves `stakeholder.cook.home` with the tick loop. These are different reasons to examine the same functionality.

```sh
metaform map identity code.timer.kitchen
```

`identity` is another provider-side relationship read. It is not an implementation of the exact relational type-equivalence definition in the [technical reference](../inference-metaform/REFERENCE.md#identity).

### Read a relationship as an object

For the join where the timer and the tick loop serve the cook:

```sh
metaform map where code.timer.kitchen full=true
metaform map node join:<join_id>
metaform map where code.loop.tick
```

A join is held by its receiver, `stakeholder.cook.home`, and holds the elements that serve its purpose, here `code.timer.kitchen` and `code.loop.tick`. The join owns its purpose, `ef` and `ifd` and has a stable id. There are no subtype joins: a part that serves the same purpose is another element held in the same join, and recording the join again with that element adds it. `children <prefix>` traverses the namespace's type ancestry toward the leaves, which is a different structure from the joins.

Use `map links <node>` for items that link to a node, and `map citing <key> <value>` for references such as an exact source path, for example `metaform map citing path src/tick.c`. Node forms are:

```text
element:<namespace-address-or-id>
join:<join-id>
```

Commands with paged results return a cursor when more data remains. Pass that returned value as `after=<cursor>`; `limit=0` requests all results. `--json` supplies structured output. `--raw`, where the verb declares it, exposes stored material outside the normal current-view filtering. A raw read is an inspection operation, not a change to selected inference context.

## Retain a finding where it matters

Memory is a graph of its own, the MCP reference memory server's: entities with a name, an entityType and observations, and relations between entities. At a node of the map it presents itself as that server, scoped to the node. A finding about a provider belongs at its element. A finding about why a specific receiver needs its providers belongs at the join.

```sh
metaform memory create_entities '[{"name":"countdown drift","entityType":"behavior","observations":["The countdown drifts one second an hour on the first board."]}]' node=element:code.timer.kitchen
metaform memory create_entities '[{"name":"display first","entityType":"behavior","observations":["The cook reads the dish name from the display, not the beep."]}]' node=join:<join_id>
metaform memory open_nodes '["display first"]' node=join:<join_id>
metaform map where code.timer.kitchen
```

`create_entities` with `node` makes each entity and ties it to the node by a join of type memory, keyed by the node's namespace address. The entity never becomes an element of the map. A later agent reading `map where code.timer.kitchen` sees the memories under `memory`: the element's own, and those on the joins it receives and provides.

Over MCP these are the commands of the tool `memory`. The second write is:

```json
{
  "command": "create_entities",
  "arguments": {
    "project": "kitchen",
    "node": "join:<join_id>",
    "entities": [{"name": "display first", "entityType": "behavior",
                  "observations": ["The cook reads the dish name from the display, not the beep."]}]
  }
}
```

### Connect, locate, and remove memories

```sh
metaform memory create_relations '[{"from":"display first","to":"countdown drift","relationType":"explains"}]'
metaform memory search_nodes countdown
metaform memory read_graph
```

A memory relation links two entities of the memory graph. It is not a replacement for the functional join's Receiving Entity, Operative Purpose, and Encounter Function.

The nine commands carry the reference server's names, arguments and results. Each takes `node`; without it, it acts on the whole graph.

| Command | What it changes or reads |
|---|---|
| `create_entities <entities>` | Makes each new entity; at a node, joins it to the node. An existing name is skipped and, at a node, joined to it. |
| `create_relations <relations>` | Adds each new relation between entities the graph acted on holds. |
| `add_observations <observations>` | Adds each observation an entity does not hold. |
| `delete_entities <entityNames>` | Deletes each entity with its observations, its relations and its joins. The map is never touched. |
| `delete_observations <deletions>` | Removes the named observations. |
| `delete_relations <relations>` | Removes the named relations. |
| `read_graph` | The graph acted on. |
| `search_nodes <query>` | Entities whose name, type or an observation holds the query, with the relations touching them. |
| `open_nodes <names>` | The named entities, with the relations touching them. |

Memory changes in place, as the reference server keeps it, with no provenance. It is kept in the project, so a clear keeps it; `metaform memory orphaned` lists the joins whose address the map no longer holds, and a new intake that holds the address reconnects them. At a node memory shows while the layer named memory reaches the node's address: `map mask <address> memory`, hiding the layer, or `--layers` without it turns it off. Each node also holds one note, at most 2048 characters, read and written with `metaform memory note <node> [text=...]`.

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

`map knowledge` writes one object per call: `op=add-element` takes an element's `address`, `name_length`, `name` and `role`; `op=add-join` takes the `receiver`, `elements`, a JSON list of the addresses that serve its purpose, `purpose`, `ef`, `ifd` and `type`, `purpose` by default. Refs are not a field of either: they live in the `sources` layer, written as items. Nothing is refused for its content: a field that is missing is stored empty and named in a notice, and a call stops only when it lacks a field its record cannot be stored without, such as a join's receiver or elements, BASE-038.

The metaform holds only elements and joins. Anything more goes in a knowledge layer, as items at the element or the join:

- The `sources` layer holds an element's refs, one item per element, written by the intake while `intake_sources` is on. It is mutable and hideable. The intake creates it already finished, so reads show it at once.
- Logic is a logic join, not a purpose join. The workflow module, which ships off and starts with `metaform enable workflow`, adds it to an element in a knowledge layer with `metaform workflow add_logic`, and it reads back with `workflow history <address> <name> <layer>`.
- A store written at an earlier layout is updated when Metaform opens it, after a copy is kept under the home's `backups` folder. At layout 19 each subtype join's element becomes held by its parent join, and what the old shape kept beyond the owner's shape moved: refs into `sources`, and a join's name, verb, non_goal and extra and a subtype join's fields into a layer named `intake details`.

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

Without a nonempty explicit layer selection, the ordinary starting set includes all finished, nonhidden layers. Local settings then remove or add participation along namespace prefixes. A local mask defaults to preserving incoming membership; a local select defaults to adding nothing. This is not a default-deny scheme.

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

Intake, knowledge, and memory have different lifecycles. The intake layer is the metaform itself, not an overlay: it is not hidden or masked, and it changes by refining, below.

## Record the condition of an object as work

The map holds the intended functional shape. The condition of an element or a join is a work record, kept apart from the map: `missing`, to be done or determined, `broken`, or `exclude`, with a note saying what and where and a task saying what it needs. Writing or changing one never changes the map and is never a refinement.

```sh
metaform map work op=add node=element:code.alarm.audible condition=broken note="The alarm pin is unconnected on the second board revision." task="Wire the alarm pin on revision two."
metaform map work node=element:code.alarm.audible
metaform map work op=done id=<work_id> resolution="Wired on revision two."
```

`op=add` returns the record's `work_id`; `op=edit` changes its condition, note, task, `held` or `reviewed`; `op=done` marks it done with its resolution kept beside it. `op=take` says an agent has started on the task: a `missing` record becomes `in-progress` and a `broken` one `fixing`, and a record taken or done cannot be taken again, so two agents never hold one task. On the map a part waiting to be built is drawn in characters, and they change faster while an agent works on it. With no `op`, `map work` lists records, by `node`, `condition` and `open=true` or `false`. At an element, the list holds its own records and those on the joins it receives or provides. Every element and join read carries `open_work`, the conditions of its open records, and `where` lists them. The intake agent writes these as it maps: `intake element` and `intake purpose` take `condition` and `note`, which write an open work record at what was just recorded. A critic writes its findings the same way, and any agent can at any time.

## Refine the metaform

The metaform is the metaform: it does not stack new layers or new colors each time something changes. The finished intake is one layer, named `intake`, and the metaform expands and changes inside it. Periodically refine it.

A refinement changes or removes one thing of the metaform and records why. No layer is named, and no id: an element is named by its `address`, a join by its `receiver` and `provider`, an element it holds.

```text
metaform map refine address=<address> <field>=<value> reason="<why it changes>" evidence="<what shows it>"
metaform map refine receiver=<address> provider=<address> <field>=<value> reason="<why it changes>"
metaform map refine address=<address> remove=true reason="<why it goes>"
metaform map history <id>
```

`evidence` is optional. Replace the angle-bracket fields with the actual addresses and reasoning. The fields to change are `name`, `name_length` and `role` for an element, and `purpose`, `ef`, `ifd` and `elements` for a join; `elements` replaces the list the join holds. Each refinement writes a new version of the thing in the `intake` layer and keeps every earlier version, so the reason for each change stays with it. `metaform map history <id>` reads every version in the order it was written, by the id that `map where <address> full=true` prints. A removal also keeps its versions. It leaves what pointed at the removed thing orphaned and names each in its result.

A finished intake also takes additions directly: `op=add-element` and `op=add-join` with `layer=intake`. Use them to expand the metaform, and `map refine` to change what is already there.

An element cannot be moved: its address is its identity, and another address is a different element. An address given as `to_address` to `map refine` for an element is not applied, and the notice says to record the element at the new address and move its joins. A join can be moved: `to_receiver` moves it to another receiver and it stays the same join. A moved join keeps its id and everything attached to it. An element recorded again at an address it held before is the same element, with its memory, items and joins.

A knowledge layer built on what a refinement changed is marked for re-examination. After examining the affected knowledge, `metaform map reexamined <layer>` records that state. Neither a refinement nor marking a layer re-examined performs the reasoning.


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

The header holds the project and Metaform selectors, **Clear project**, and a **Layers** button that counts the layers shown, such as `Layers · 3 of 5`, and opens a checklist with one row per layer and **Apply to folder** at its foot. The left pane holds the two-dimensional map, with **Back**, **Forward**, the breadcrumb and **Fit** on a strip above it, and three inspection tabs: **Object**, **Provenance** and **Prompt**. The three-dimensional graph fills the right, and every item of the layers turned on is its own node there. Select a graph object to inspect its recorded content. In the 2D view, use Fit or `F`; the 3D view supports orbit, zoom, selection, and layout controls.

The checklist selects what the view presents. **Apply to folder** persists the chosen layer context for that folder. A temporary visual selection and the folder's working context are different operations.

The page shows each node's condition from its work records: a node with an open `missing` record is drawn at 70% opacity and turns solid once its task is done, one with an open `broken` record flashes red, and `exclude` keeps its look. The Object panel lists the selected object's records with their note, task, held and reviewed flags, and the resolution once done.

The page follows the map without polling. After any command that changes a project's map, on the command line or over MCP, and after the page's own writes, `map.changed` is announced and the server pushes it to every open page, which redraws without a reload. An intake being recorded is drawn as each object arrives.

The Prompt tab exposes existing prompt versions, comparisons, and **Save as new version**. It does not generate a lexicalized prompt merely because it displays prompt records.

**Clear project** in the header does what `metaform clear project <project> --confirm` does for the selected project: it removes the project's metaforms and report files and keeps its registration, folder, settings, origins and variants. It first shows the command's own caution and asks on the page. Afterwards every open page shows the project with no metaform until the next intake.

## Retain and exchange the work

Write the map as a short Markdown document, to read or to pass on:

```text
metaform map markdown file=kitchen-map.md
metaform map markdown address=code.timer.kitchen
```

It holds each element's name, address, role and paths, and each join's receiver, the elements it holds, `ef` and purpose. The paths come from the `sources` layer. With an address it covers that element and what stands around it. The web GUI's Export button saves the same document.

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

Artifact variants, layer provenance, the version history of the metaform, and prompt versions are distinct records. They become a connected account of a task when the actual associations are recorded; the presence of each facility is not proof that every producer automatically records every association.

## Reports and further reading

```sh
metaform list reports
metaform read report <file-name>
metaform feedback "<observation about the process>"
```

Report records can be associated with projects and layers. `feedback` also accepts report and partial-shape material; use `metaform help feedback` for its exact text/file/stdin forms.

For interpretation rather than command execution, continue with [Reading an Inference Metaform](reading-a-metaform.md). For a capability that should become a reusable module, use [Extending Metaform](extending-metaform.md). The [implementation map](../inference-metaform/IMPLEMENTATION_MAP.md) is the source-level companion to this guide.
