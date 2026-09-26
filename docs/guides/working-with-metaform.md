# Working with Metaform

[Documentation](../README.md) · [Getting started](getting-started.md) · [Reading the representation](reading-a-metaform.md)

Use Metaform to bring prepared understanding into a task, examine the relevant relationships, and retain what the work establishes. The examples below use the supplied project map imported as `reference-demo` in [Getting started](getting-started.md#inspect-the-supplied-project-map-without-a-new-intake). For another workpiece, use the addresses returned by its own map.

## Establish the current work context

```sh
metaform
metaform list projects
metaform list metaforms
metaform config --show
```

The current folder supplies context. A registered project establishes its default, and folder settings can select a different project or layer set. A project may contain multiple Metaforms; one is active.

```sh
metaform set --project reference-demo
metaform activate metaform main
```

`set` persists the selection for the folder. To return to the folder's inherited/default project choice:

```sh
metaform unset --project
```

A module call can instead use `--project reference-demo` for that invocation. MCP tools accept the corresponding `project` argument. Use these explicit choices when an agent starts outside the workpiece folder; do not assume that a host's folder and your terminal's folder are the same.

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
metaform map search "module"
metaform map element code.system.plugin
```

`search` is a text search over stored content, not a separate semantic retrieval model. `element` returns the descriptor, including the project name and references. For this example, the functional address names a plugin system and the project calls it the **module contract and loader**.

Now look in both directions:

```sh
metaform map joins code.system.plugin as=receiver
metaform map joins code.system.plugin as=provider
```

As a receiver, an entity exposes what it needs. As a provider, it exposes whose purposes its effects serve. The provider view for the module contract includes the module author, chassis, command line, MCP server, builder, and agent instructions. These are different reasons to examine the same functionality.

```sh
metaform map identity code.system.plugin
```

`identity` is another provider-side relationship read. It is not an implementation of the exact relational type-equivalence definition in the [technical reference](../inference-metaform/REFERENCE.md#identity).

### Read a relationship as an object

For the recorded module-author relationship:

```sh
metaform map node join:d14bd3498b614dfbaf0754c99b28dba3
metaform map subtypes d14bd3498b614dfbaf0754c99b28dba3
metaform map where code.template.module
```

The join owns its purpose and has a stable ID. Its internal subtypes explain contributions within that relationship. `where` finds an internal subtype and its containing join; it does not promote that subtype to a global element. `children <prefix>` traverses the namespace's type ancestry, which is a different structure from the provider/receiver joins.

Use `map links <node>` for items that link to a node, and `map citing <key> <value>` for references such as an exact source path. Node forms are:

```text
element:<namespace-address-or-id>
join:<join-id>
subtype:<namespace-address-or-id>
```

Commands with paged results return a cursor when more data remains. Pass that returned value as `after=<cursor>`; `limit=0` requests all results. `--json` supplies structured output. `--raw`, where the verb declares it, exposes stored material outside the normal current-view filtering. A raw read is an inspection operation, not a change to selected inference context.

## Retain a finding where it matters

An observation about a provider belongs at its element. A finding about why a specific receiver needs that provider belongs at the join. A note about an absorbed implementation contribution can belong at the subtype.

The following are example notes written by the commands, not quotations from the original intake:

```sh
metaform memory add-observations element:code.system.plugin "The template and helloworld share the module-author purpose join."
metaform memory add-observations join:d14bd3498b614dfbaf0754c99b28dba3 "Extension entry points and CLI/MCP surfaces come from the module contract."
metaform memory open-nodes join:d14bd3498b614dfbaf0754c99b28dba3
```

The first write creates the memory layer. A subsequent agent can recover the finding by the relationship's address rather than rediscovering which free-floating note concerned this receiver's purpose.

The MCP equivalent of the second write is the tool **`memory_add-observations`** with:

```json
{
  "project": "reference-demo",
  "node": "join:d14bd3498b614dfbaf0754c99b28dba3",
  "text": ["Extension entry points and CLI/MCP surfaces come from the module contract."]
}
```

Tool names use an underscore between module and verb and retain hyphens **within** a verb. Thus `memory_add-observations` is the actual name, not `memory_add_observations`.

### Connect, locate, and remove memories

```sh
metaform memory create-relations element:code.system.plugin exemplified-by subtype:code.module.example
metaform memory search-nodes "module"
metaform memory read-graph
```

A memory relation is an item linking two nodes, with a relation label. It is not a replacement for the functional join's Receiving Entity, Operative Purpose, and Encounter Function.

The module exposes nine operations:

| Operation | What it changes or reads |
|---|---|
| `create-entities <address> <type>` | Creates or locates a graph element for memory use. Existing functional nodes need no duplicate entity first. |
| `create-relations <from> <relation> <to>` | Adds a linked memory item. |
| `add-observations <node> <text>...` | Adds observations at the node. |
| `delete-entities <node>...` | Deletes memory items at those nodes, **not** the underlying graph identities. |
| `delete-observations <node> <text>...` | Removes the matching observation text. |
| `delete-relations <from> <relation> <to>` | Removes matching linked memory items. |
| `read-graph` | Reads the participating memory graph. |
| `search-nodes <query>` | Searches memory content. |
| `open-nodes <node>...` | Reads memory at the named nodes. |

Memory changes in place. This build does not give memory its own revision history or provenance ledger. Its direct write path can address retained memory even when the current context masks it. The current read view still follows layer participation.

## Keep a body of knowledge as a layer

A layer identifies a question or variable and retains the values contributed in answer to it. A review might answer what was established about module behavior; a practice layer might carry general engineering knowledge; an imperative layer might carry selected instructions for an operation. These purposes are not interchangeable.

Create a review layer and add a local finding:

```sh
metaform map knowledge op=create layer=review-notes variable="What this review established." mutable=true hideable=true
metaform map knowledge op=add-item layer=review-notes node=element:code.system.plugin value='{"finding":"The CLI and MCP read the shared verb declarations."}'
metaform map knowledge op=finish layer=review-notes
```

These shell examples use POSIX-style single quoting around JSON. The tool equivalent supplies the JSON value as structured data rather than a shell string. For example, `map_knowledge` accepts `op`, `layer`, `node`, `value`, and `project` as named arguments.

The layer starts **building**. Finishing makes it available to normal selection. The returned layer name is authoritative: a name already used by a different declaration can result in a numbered name and notice. Read operation results rather than assuming every requested name was installed unchanged.

```sh
metaform map layers
metaform map layer review-notes
metaform map node element:code.system.plugin
```

`layer` reads the named layer directly. `node` groups participating items by layer at that node. A node-local item does not become inherited knowledge merely because its address has ancestors.

### Place general knowledge at its applicable type

A **property** is the store's branch-scoped knowledge mechanism. Unlike a local item, it travels the namespace. For an illustrative informational property:

```sh
metaform map knowledge op=add-property layer=review-notes element=type:code value='{"information":"General code guidance applies to descendants of code."}'
metaform map context code.system.plugin
```

This is a demonstration of placement, not an added rule that every task must follow. The `type:` form targets a namespace prefix even when it has no independently represented global element. A property at `code` applies to its descendants. Properties attached toward the leaves from the current scope can be **visible** from an ancestor without thereby applying to every sibling branch. The context result separates `applying` and `visible`.

Properties implement scoped context support; they are not, by themselves, a producer that derives every semantic consequence of an Encounter. [Encounter propagation](../inference-metaform/REFERENCE.md#encounters) explains the full mechanism and [the implementation map](../inference-metaform/IMPLEMENTATION_MAP.md#selection) locates its current support.

When creating a layer derived from other layers, the `sources` JSON array records those source layer names or IDs. Optional provenance fields include `module`, `workflow`, `prompt`, `model`, `role`, and `blinded`. Record the actual inputs and execution identity; the store does not discover all derivation links automatically.

## Select the understanding for a task

Without a nonempty explicit layer selection, the ordinary starting set includes all finished, nonhidden, non-correction layers. Local settings then remove or add participation along namespace prefixes. A local mask defaults to preserving incoming membership; a local select defaults to adding nothing. This is not a default-deny scheme.

For example, temporarily exclude review notes from the `code.system` branch, then restore them specifically for the plugin-system branch:

```sh
metaform map mask code.system review-notes
metaform map select code.system.plugin review-notes
```

The descendant selection does not turn those notes on for siblings. Remove these local choices with:

```sh
metaform map clear code.system.plugin review-notes select
metaform map clear code.system review-notes mask
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

Corrections can mark dependent knowledge as requiring re-examination. After examining the affected knowledge, `metaform map reexamined <layer>` records that state. Neither finishing a correction nor marking a layer re-examined automatically performs the reasoning.

The current `map knowledge` interface does not expose the typed `ef` field, although intake and the Python store support it. Do not use the descriptive `function` text as a substitute for the Function/Encounter flag. [Correspondence issue C01](../inference-metaform/IMPLEMENTATION_MAP.md#c01) identifies the exact omission.

## Use prompting and criticism without changing the assignment

Project-grounded lexicalization first resolves a request's generalized referents to recorded project names and functional addresses. It replaces the corresponding terms while retaining the requested operation, then provides mappings and knowledge directions. It stops before execution. The [walkthrough](../examples/project-walkthrough.md#4-lexicalization-before-execution) shows the transformation and the actual reads supporting it.

There is no shipped lexicalization verb in this edition. The present name, graph, context, memory, and prompt-version facilities are available to an agent or module implementing that operation. Existing prompts can be listed and inspected with `metaform prompts` and `metaform prompt <name> [version-number]`; the GUI can save new versions of existing prompts. Prompt storage is not itself the lexicalizer.

Selected memory may be **information** to reason from, or **additional imperatives** when its layer has that purpose. An informational observation does not silently rewrite the task. Explicitly selected imperative knowledge can supply instructions and acceptance criteria separately from the lexicalized request.

### Respond substantively to a blindspot challenge

A critic can work with the actual source and Metaform together, or examine the Metaform alone. The project response establishes one of three substantive outcomes:

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

The interface supplies project and Metaform selectors, layer controls, two-dimensional and three-dimensional graph views, and four inspection tabs: **Object**, **Provenance**, **Prompt**, and **Corrections**. Select a graph object to inspect its recorded content. In the 2D view, use the fit control or `F`; the 3D view supports orbit, zoom, selection, and layout controls.

Layer chips select what the view presents. **Apply to folder** persists the chosen layer context for that folder. A temporary visual selection and the folder's working context are different operations.

The Prompt tab exposes existing prompt versions, comparisons, and **Save as new version**. It does not generate a lexicalized prompt merely because it displays prompt records. The Corrections tab presents the relevant retained changes rather than editing the runtime source.

## Retain and exchange the work

Export the current project to an existing destination directory:

```sh
metaform export file=metaform-export.json
```

Narrow the export by Metaform or layer when useful:

```text
metaform export reference-demo file=main-export.json metaform=main
metaform export reference-demo file=layer-export.json layer=<layer-name>
```

Import into a registered project with:

```sh
metaform import metaform-export.json reference-demo
```

Exchange preserves IDs and adds missing records. It does not overwrite an existing identity with a later copy of the same ID. A Metaform already owned by another project in the same home is not duplicated into a second owner; the import reports that condition. This is exchange of retained representation, not Canonical Intake submission.

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
