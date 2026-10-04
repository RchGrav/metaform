# A task grounded in Metaform's own module system

[Documentation](../README.md) · [Reader guide](../guides/reading-a-metaform.md) · [Module-author guide](../guides/extending-metaform.md)

This walkthrough uses the actual [September 26, 2026 project export](project-metaform.json), this repository's own map as it was recorded that day. Its graph records are recorded material. The task, lexicalized request, criticism exchange, and prospective reuse described below are **derived illustrations**, not a transcript of a completed agent assignment. The export is a dated snapshot of an earlier version, schema version 1, which the current chassis does not import; the inspection commands are the reads that return records of this kind from a map that holds them. In that export the project's names are descriptor items at the elements, where the current store holds them on the elements as `name`, and each subtype is its own row, where the current store has no subtype joins: the join holds the element. Each join also names one `provider`, where a current join holds a list of `elements`, and carries `function`, `relation`, `observation` and `non_goal`, which the current shape does not have. The [reader guide](../guides/reading-a-metaform.md) lists the differences.

## 1. Begin from a receiving purpose

Suppose the task is:

> Add a module that examines the knowledge attached to a functional relationship.

The project already represents a relevant receiver: `stakeholder.author.module`, named **module author**. The provider is `code.system.plugin`, named **module contract and loader**. Their join is `d14bd3498b614dfbaf0754c99b28dba3`.

The recorded purpose is to add a capability once, as a module, with command and MCP surfaces, settings, events, status, and lifecycle, without changing the chassis. The record's Encounter Function describes a `MODULE = Module(...)` declaration and discovery from bundled folders, the user's home, or installed entry points.

```sh
metaform map element code.system.plugin
metaform map node join:d14bd3498b614dfbaf0754c99b28dba3
```

An agent now receives more than a list of files. It has a reason to use the shared contract, the distinction between the module's contribution and the chassis's contribution, and locations for the relevant implementation. The graph has already performed part of the semantic preparation for the assignment.

## 2. Identify the actual starting materials

Two internal subtypes belong to this join in the snapshot. In the current shape the join holds them as elements:

| Address | Project name | Contribution |
|---|---|---|
| `code.template.module` | template | The empty module declaration from which a new capability can start. |
| `code.module.example` | helloworld | Working demonstration of verbs, settings, events, storage, async execution, and status. |

Read their operative code at [template](../../src/metaform/modules/template/__init__.py) and [hello](../../src/metaform/modules/hello/__init__.py). The [module contract](../../src/metaform/module.py), [loader](../../src/metaform/loader.py), and [store](../../src/metaform/data/store.py) supply the shared facilities.

The project export also contains observations about documentation and planned mechanisms. Those observations remain part of the recorded graph, but the extension instructions here are grounded in the included code. A record referring to an omitted document is not a substitute for its contents.

For the new relationship-inspection capability, a module can receive `ctx.store`, parse a node, and call the existing node/layer reads. It does not need a separate database or a second memory-addressing scheme. The complete example in the [extension guide](../guides/extending-metaform.md#start-a-module-from-the-template) shows that use of the contract.

## 3. Examine the same provider through other receivers

```sh
metaform map joins code.system.plugin as=provider
```

The original export contains these six receiving relationships:

| Receiver | Why it receives the plugin system |
|---|---|
| module author | Declare a capability once and obtain the supported module facilities. |
| chassis | Discover, load, and withdraw module contributions. |
| command line | Obtain verbs and their input/settings declarations. |
| MCP server | Obtain the currently surfaced tool declarations. |
| package builder | Identify loaded modules and their dependencies. |
| agent instructions | Obtain each surfaced module's purpose and current notice. |

This exposes the relevant perspectives before implementation begins. The extension task can be considered in terms of what each receiver needs. It does not require recreating six registration systems, nor does it automatically expand the task into changes to all six consumers.

## 4. Lexicalization before execution

A different request concerns the same provider:

```text
Review error handling in the plugin system.
```

A project-grounded lexicalization is:

```text
Review error handling in the module contract and loader.
```

Accompanying orientation:

```text
Canonical project term -> functional address
module contract and loader -> code.system.plugin

Related understanding
provider-side purpose joins for code.system.plugin
selected items at element:code.system.plugin
selected items at the relevant join IDs
source references retained by those records
```

The operation, **review error handling**, is unchanged. The generalized referent is resolved to the project's recorded name. The orientation tells the executing agent where to obtain relevant understanding and memories; it does not carry out the review or invent a new goal. Selected imperative layers, when used, are separate contributions with their own purpose.

This is the intended lexicalization operation. The current source supplies names, joins, node reads, layers, memory, and prompt storage, but not a shipped producer that performs this preprocessing automatically. The example therefore shows the design precisely without claiming a tool invocation that does not exist.

## 5. Challenge a possible omission

A critic examining the new module might ask whether it needs its own settings-persistence implementation.

A substantive **C response** would identify the existing implementation: the module declares settings with `metaform.settings`; the chassis resolves and retains them, exposes the corresponding controls, and preserves stored values when the module is disabled. The response names [settings.py](../../src/metaform/settings.py), [home.py](../../src/metaform/home.py), and the module-author purpose served by the contract. That is an explanation of where the apparent omission is fulfilled, not a dismissal because a graph edge was already visited.

If a different concern had been considered and rejected, an **A response** would preserve the reason it adds no benefit. If it revealed an unexplored relevant issue, a **B response** would explain that relevance. The alphabetic state is the recorded disposition; the reasoning is the substance of the exchange.

The current `map answer` operation stores state, an optional link, and time. It does not write the rationale automatically. Existing item/layer storage can retain the explanation, while an integrated producer remains construction work.

## 6. Retain what later work should not have to reconstruct

After examining the source, an agent can leave an observation at the precise receiving relationship:

```sh
metaform memory create_entities '[{"name":"settings persistence","entityType":"fact","observations":["Module settings persistence is supplied by the chassis; declarations appear in settings.py and are retained through home.py."]}]' node=join:d14bd3498b614dfbaf0754c99b28dba3
metaform memory open_nodes '["settings persistence"]' node=join:d14bd3498b614dfbaf0754c99b28dba3
```

These commands create a local example memory; the sentence is not present in the supplied original export. A subsequent agent can retrieve it at the join that gives it meaning. A general conclusion intended to participate in several tasks can instead be recorded in a purpose-named knowledge layer, with source/provenance associations.

The memory write alone does not certify a review result or version the finding. Memory is mutable in this edition. A refinement of the represented graph is a new version in the `intake` layer; a versioned prompt uses the prompt store; a captured implementation result uses artifact history. Their different lifecycles make it important to record the association actually produced.

## What this example demonstrates

The original intake has already established the functional provider, its receiving purposes, the contribution of the template and example, and the project names needed to refer to them. Later tasks can reuse that understanding to implement, review, criticize, or retain findings. A new conclusion can become material for another round of inference.

The example does not reduce the method to module development. The same relationship-oriented preparation can concern a document's argument, a narrative's functional parts, or an image's contribution to a collection. The artifact-specific understanding changes; the connection between prior inference, meaningful addresses, and subsequent reasoning remains.
