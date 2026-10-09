# Reading an Inference Metaform

[Documentation](../README.md) · [Operating guide](working-with-metaform.md) · [Project walkthrough](../examples/project-walkthrough.md)

An Inference Metaform is a representation of **what a workpiece is doing**. Its addresses organize functional meaning; its joins explain receiving purposes and how providers serve them. It is not a source-file hierarchy or a call graph with more descriptive labels.

This guide reads the earlier map of this repository, recorded on September 26, 2026 and kept as a dated snapshot, an [export](../examples/project-metaform.json) of an earlier version, at schema version 1. The current chassis imports schema version 19 only, so that file cannot be imported into it; the commands below are the reads that return records of this kind from a map that holds them, and on your own map they take its addresses. The recorded map has 19 global elements, 33 require joins, and 26 internal subtypes. Its 86 type-prefix records are the ancestry needed for the namespace, not 86 independently represented subsystems. The [implementation map](../inference-metaform/IMPLEMENTATION_MAP.md#graph-index) contains the complete element, join, and subtype index.

The snapshot has the shape of its day, and the current shape is smaller. The owner restored his original shape on 2026-10-04. An element is its `namespace_address`, `name_length`, `name` and `role`. A join is its type, `purpose`, `ef` and `ifd`, held by its receiver, and it holds the elements that serve it. Compared with the snapshot:

| In the snapshot | Now |
|---|---|
| The project's name for a functionality was a descriptor item at the element, then a `name` on the join. | `name` is a field of the element. |
| A join named one `provider`. | A join holds a list of `elements`. |
| A subtype was its own row, or a join of type `subtype` inside its parent join. | There are no subtype joins. The element is held by the join. |
| A join carried `function`, `relation`, `verb`, `observation`, `non_goal` and `extra`, and `ef` was one word, Function or Encounter. | A join carries `purpose`, `ef` and `ifd`. `ef` is the Encounter Function written as an active-voice fragment, and `ifd` is `sends`, `receives` or `both`. |
| Refs were a field of an element or a join. | Refs are items in a knowledge layer named `sources`. |
| The condition of an object was a finding with a `flag`. | It is a work record, apart from the map. |

Opening an older store upgrades it in place, after a backup, and moves what the old shape kept into the `sources` layer and a layer named `intake details`.

The running web GUI draws a map as nodes and joins. This screenshot is the kitchen timer's map from [Getting started](getting-started.md#record-a-small-map-by-hand), taken from a throwaway home: elements as nodes in the 3D graph, each join drawn as a vertex between its receiver and the elements it holds, the audible alarm red for its open `broken` work record, and the selected element's `sources` refs, a review-notes item, memory and the joins it holds and serves in the Object panel on the left. The 2D map above the panel is zoomed in on the kitchen timer and the tick loop.

![The Metaform web GUI: the kitchen timer selected in the Object panel on the left, with its sources path, a review-notes item, its memory and the joins it holds and serves, the 2D map above it, and the 3D graph on the right with the audible alarm red for its broken work record.](../images/gui-map.png)

## Begin with the artifact and its receivers

The exported project's Artifact Under Examination, or **AUE**, is `code.graph.knowledge`, named **Metaform**. Its outside vested receivers include:

| Address | Project name | Perspective |
|---|---|---|
| `stakeholder.orchestrator.agent` | agent orchestrator | Receives a functional map and the facilities through which agents use it. |
| `stakeholder.author.module` | module author | Receives an extension mechanism for adding a capability without changing the chassis. |

These are types of parties vested in this kind of artifact, not identifiers for the particular people reading this guide. The intake identifies vested parties through the purposes that drive improvement in the artifact. It does not simply label whoever requested the intake as the CQU.

The map names `code.chassis`, **chassis**, as its Defining Element. The represented supporting capabilities include the store, command line, plugin system, intake, map API, memory, MCP, GUI, variants, installer, builder, reports, agent instructions, and tests. This is the functional organization recorded by this intake, not a claim that every implementation component must appear as a separate global node.

Inspect the outside receiving perspective with:

```sh
metaform map element stakeholder.author.module
metaform map joins stakeholder.author.module as=receiver
```

Ask what that party receives, not just which box sits beside it in a drawing.

## Distinguish entity, element, and role

An **Entity** is a whole at the scope of examination. An **Element** is a nameable part in relation to that whole. When you examine a component's own requirements and composition, you treat it as an entity with its own elements. One identity can therefore be a provider in one join and a receiver in another.

The intake's roles distinguish contributions:

| Role | Meaning in the examined artifact |
|---|---|
| AUE | The artifact or collection under examination. |
| CQU | A vested party outside the AUE whose purpose is being served. |
| DE | The defining element whose loss would prevent the AUE from remaining the same type. |
| SE | A substantial element whose Encounter Function helps the defining element serve the vested purpose. It counts as substantial because of what it is meant to contribute to the AUE, even when that contribution is weak or replaceable. |
| NE | A notable element expressing an essential demand or requirement on the external environment. |

A **Providing Element**, or **PE**, is an endpoint role in a join, not another element-role attribute. **Parametric** qualities and quantities are tunable details, not automatically separately named elements. Something being recognizable or nameable does not make it a load-bearing independent part of this map.

“Exterior” means outside the project. “External” can mean outside the functionality being examined while still inside the repository. Ownership is not the distinction. A subsystem inside the repository can provide something that the currently examined subsystem receives from outside its own boundary.

## Read the namespace and the project name separately

For `code.system.plugin`, there are three useful readings:

| Field | Value |
|---|---|
| Address | `code.system.plugin` |
| Full type reading | plugin system code |
| Short type name | plugin system (`name_length = 2`) |
| Project name | module contract and loader |

Namespace segments reverse into a readable type name; underscores become spaces. `name_length` selects how many trailing segments participate in the short reading, and that short reading is the element's name. The current store records the project name on the element, as `name`: it is how this project names the functionality, formally or informally. The export, written before that change, holds it in a descriptor item at the element.

Every prefix supplies a type perspective:

| Prefix | Type reading |
|---|---|
| `code` | code |
| `code.system` | system code |
| `code.system.plugin` | plugin system code |

The address can orient inference before the project-specific joins are read. The joins then connect that general understanding to the particular workpiece. Both are necessary to the account: the type tells an agent what kind of thing it is considering, while the receiving relationships establish what that thing is doing here.

### An address is a prompting surface

The author's address-only material contains four generated lists requested with `write 10 best practices for [address]`. The addresses were `code`, `code.engine`, `code.engine.game`, and `code.engine.game.fps`; no project description or code accompanied them. Guidance shifted from general programming concerns to engines, game engines, and first-person game engines.

The point is not to install those generated lists as universal requirements. It is that a meaningful type address engages existing understanding and supports further inference. A practice that remains applicable after removing a leaf belongs at a broader type. A specialized practice about hit registration does not become a rule about all code merely because an ancestor can see it.

Original material: [address-only examples](../../specifications/metaprompting_element_segments_example.md). Full explanation: [primordial type understanding](../inference-metaform/REFERENCE.md#type-understanding).

## Read a join as a reasoned relationship

The module author receives a capability from `code.system.plugin`. In the snapshot this join is:

```mermaid
graph LR
    receiver["stakeholder.author.module<br/>module author"]
    provider["code.system.plugin<br/>module contract and loader"]
    provider -- "ef: Encounter" --> receiver
```

| Field | Value |
|---|---|
| Receiver | `stakeholder.author.module`, owns the Operative Purpose: add a capability once, as a module, with the needed surfaces |
| Provider | `code.system.plugin`, supplies the Encounter Function: a MODULE declaration and loader through which that capability becomes commands, tools, settings, events, status, and lifecycle |
| Join | `d14bd3498b614dfbaf0754c99b28dba3` |
| `ef` | Encounter, the snapshot's one-word marker |
| `relation` | The plugin system lets a module author plug a capability into Metaform with one declaration. |

This display is an abbreviated reading of the snapshot's record, which also holds `function`, `observation`, references and a null `verb`. In the current shape the same join is held by `stakeholder.author.module`, holds `code.system.plugin` among its elements, and carries `purpose`, `ef` and `ifd`. On a map that holds it, the element's address read prints the join under `provides`, and `map node` prints what the layers hold at the join:

```sh
metaform map where code.system.plugin
metaform map node join:<join_id>
```

The **Operative Purpose** is the why, held by the receiver. The **Encounter Function** is the how, supplied by the elements the join holds for that relationship, and the current `ef` states it as an active-voice fragment that starts with its third-person verb. `ifd`, the information flow direction, says which way the primary flow runs: `sends` from the Operative Purpose to the Encounter Function, `receives` from the Encounter Function to the Operative Purpose, or `both` when the need is equal. Anything the old shape kept in `observation` or `non_goal` is not a field now. It belongs in a knowledge layer, as an item at the join, where a reader can see which layer asserts it.

A provider can serve different purposes through different Encounter Functions. The module contract serves the command line by supplying verb declarations, the builder by identifying loaded modules and dependencies, and the module author through the declaration-and-loading encounter. Those distinctions belong in the joins, one per receiving purpose, not in a single flattened element-level function description.

## Function and Encounter are not synonyms for function and file

**Function** is operative capability. **Encounter** is the form through which it is expressed, realized, used, or experienced. In the snapshot's module-author join, the declaration mechanism is marked Encounter; in the command-line receiving join, supplying the declared verbs is marked Function. The current `ef` does not carry that mark. The Encounter Function is written out in the join's `ef` text.

The phrase **Encounter Function** has an intentional **Unloaded Definition**. It supports understanding the function of an encounter or the encounter of a function according to the artifact and relationship. Replacing it everywhere with “callable,” “API method,” or “user interface” would remove part of the method's scope.

This matters outside software as well. In the author's photograph example, a couple can be the defining subject while a tower supports the setting. What the tower contributes to the photograph is not the same question as what that structure does independently in the world. Nearby images or the folder context may support an inference about the occasion. Classifying the image as scenery does not replace the description of its particular subject.

The dotted typology expresses valid Function or Encounter types, not every convenient metadata label. Encoding alone does not make a functional type. A JPEG encoder can have an encoder-function address; simply appending a file format to a document address does not establish such a function. The [namespace account](../inference-metaform/REFERENCE.md#namespaces) covers the distinctions in depth.

## A join holds the elements that serve its purpose

The module-author join holds two elements besides the contract itself in the snapshot:

```mermaid
graph TB
    join["join held by stakeholder.author.module<br/>purpose: add a capability once, as a module"]
    join -.holds.-> plugin["code.system.plugin<br/>module contract and loader"]
    join -.holds.-> template["code.template.module<br/>template"]
    join -.holds.-> example["code.module.example<br/>helloworld"]
```

`template` contributes a contract-shaped starting point. `helloworld` demonstrates working use of the contract. The snapshot kept them as subtype joins inside the parent join. The current shape has no subtype joins: the join holds each of them as an element, and each stays one ordinary element record at its own address. `map where <address>` returns the join that holds it. They do not receive independent copies of the purpose merely because they can be named.

```sh
metaform map where code.module.example
```

Recording a join again with an element it holds adds the elements it does not hold, which is how the intake anneals parts into one join. This is the result of convergence: many implementation details are absorbed into load-bearing functionalities while their atomic contributions remain available as held elements. Convergence is not loss of the useful detail; it is the decision about where that detail belongs.

The runtime can also create a memory holder named `code.module.hello` when the hello demo runs. That holder is not the same address as the element `code.module.example` that the snapshot's subtype join held. The former is a module-created location for greeting records; the latter describes the example module's contribution to the module-author purpose. Similar names do not silently merge their identities.

## Follow Encounters through the applicable structure

Consider the author's language example. A C Encounter, `code.c`, is attached at `code.utility.disk`. The functional address remains the disk utility; the language is not appended as `code.utility.disk.c`.

```mermaid
graph LR
    disk["code.utility.disk<br/>(code.c attached here)"] --> utility["code.utility"] --> trunk["code"]
    disk -.forward application.-> descendants["descendants of code.utility.disk"]
```

Unrelated siblings do not acquire C through the common ancestor.

The relevant consequences include memory semantics, data representation, interfaces, error behavior, and operating-system interaction. An agent can examine those consequences through the disk utility's receiving purposes, not merely paste a generic C checklist beside it. A mixed-language workpiece retains the attachment points where each language actually participates.

The store's `map context <address>` separates applying properties from visible properties. This supplies scope-aware knowledge access. The general Encounter-inference producer and the full language-Encounter account extend beyond that one read operation. The served intake also includes a language-address exclusion that differs from the author's broader Encounter account. [The implementation map](../inference-metaform/IMPLEMENTATION_MAP.md#correspondence) preserves that specific boundary instead of silently changing either account.

## Identity is relational, not just a stable label

The exact semantic definition is:

```text
C(T) = { (r_i AND p_i AND e) }
```

Here `r_i` is a Receiving Entity, `p_i` its Operative Purpose, and `e` the single Encounter Function at the represented resolution. The set is exact: not a similarity score, a minimum list of attributes, or an approximate signature.

A realization can change while preserving the relevant relational identity. Changing an identity-defining relationship changes the semantic type. Keeping a useful functional address during a port does not prove that the Encounter-specific identity is unchanged; language may be materially part of that Encounter.

The exported graph's broad provider records contain receiver-specific joins. The existing `map identity` command retrieves those joins. It does not prove exact equivalence between implementations or supply an otherwise unspecified mapping from every broad provider record to the formal type `T`.

## Distinguish the representation from attached knowledge

An element or a join provides an address. Items attach local findings, observations, or other values at that address. Properties supply branch-scoped knowledge. Layers keep bodies of knowledge and their purposes distinct; selection determines which participate in an operation. Refinements retain changes to the representation as versions in the `intake` layer.

```sh
metaform map node element:code.system.plugin
metaform map context code.system.plugin
metaform map layers
```

The supplied original project export contains one intake layer and no memory or property records. The store's ability to hold those records is nevertheless implemented. Later local exercises can add them without changing what the original export demonstrates.

An agent can use prepared understanding, derive another conclusion, and retain it at a meaningful location. Subsequent inference then works on that result as well as the original graph. This continuing use is why the Metaform is both **derived from inference** and **a guide for inference**.

For executable layer and memory procedures, return to [Working with Metaform](working-with-metaform.md). For the connected account of prompting, criticism, provenance, and shaping a workpiece through intent, read the [preprint](../preprint/inference-metaform.md).
