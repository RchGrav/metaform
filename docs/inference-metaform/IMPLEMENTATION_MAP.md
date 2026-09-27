# Inference Metaform: implementation map

[Technical reference](REFERENCE.md) | [Examples to collect](EXAMPLES_TO_COLLECT.md) | [Ideas](IDEAS.md)

This document connects the [described mechanisms](REFERENCE.md) to the source on the `chassis` branch, the project's earlier recorded map, the operative resources, and the tests. It separates implemented facilities from the producers that use them and keeps specific source/intent differences at their actual locations.

## Contents

1. [Snapshot and evidence basis](#snapshot)
2. [Mechanism correspondence at a glance](#overview)
3. [Records, names, relationships, and reads](#records)
4. [Canonical Intake: resource to stored result](#intake)
5. [Selection, properties, and visibility](#selection)
6. [Memory](#memory)
7. [Corrections and re-examination](#corrections)
8. [Prompt versions and lexicalization](#prompts)
9. [Blindspot challenges and plans](#challenges)
10. [Community extension and execution facilities](#extensions)
11. [Event delivery and the earlier illustration](#events)
12. [Other implemented project capabilities](#supporting)
13. [Localized correspondence issues](#correspondence)
14. [Tests and available operational evidence](#tests)
15. [Complete index of the September 26 map](#graph-index)

<a id="snapshot"></a>
## 1. Snapshot and evidence basis

### Source identity

This map follows the `chassis` branch after build step 62, commit `2e6f581`, as revised for step 58 of the [build log](../../specifications/spec/BUILD-LOG.md). It was first written on September 26, 2026 against the supplied bundle attributed to commit `ce9062bdec9398ca1f23ac60684bd3cc7e37f23c`; [the edition notes](../EDITION.md) record that edition and what has changed since.

The operative intake resource is:

```text
src/metaform/modules/intake/resources/Canonical_Intake.xml
```

It is byte-identical to `specifications/Canonical_Intake.xml`, and a test fails when the two differ. Its SHA-256 is:

```text
9554f5b82674fb0ce2fb61381022d49cd9c45071401c5f8c433770e27f3feab6
```

### The earlier map used as the example

The standalone project JSON, [project-metaform.json](../examples/project-metaform.json), is an export of an earlier version: the supplied `exports/metaform-main.json` of September 26, 2026, at schema version 1, with one change, each join and subtype row recording `verb` as null because that intake was made before `verb` existed. The current store is at schema version 5 and does not import it. Its Metaform is named `main`, id `6a339171fe6f44c49a40f4a270d98913`, with intake layer `2f6b86ffc49c4575bfdbf0ad2ac712f7`, named `intake-20260926T192840Z-f04016`, created September 26, 2026 at 19:28:40 UTC. Its recorded result id is `metaform-intake-20260926-a823b992`.

The export's record shapes are those of that day. The project's names are descriptor items at the elements, where the current store holds them on the joins as `name`. Each subtype is its own row with its own id, where the current store holds a join of type `subtype` inside its parent join, holding an ordinary element. The condition of an object is a finding with a `flag`, where the current store holds work records apart from the map.

| Stored material in the September 26 export | Count |
|---|---:|
| Type-prefix records | 86 |
| Global elements | 19 |
| Purpose joins | 33 |
| Internal subtypes | 26 |
| Descriptor items | 19 |
| Properties | 0 |
| Refs | 98 |
| Intake layers | 1 |
| Provenance records | 1 |
| Findings | 5 |
| Report records in SQLite | 2 |
| Challenge states / plans | 0 / 0 |

Selections and the correction stack are empty in this export. These counts identify stored material; they do not define the capabilities of the store.

### What was checked

The September 26 edition used static source inspection, the supplied source-review results, archive hash verification, export inspection, and a read-only SQLite integrity/count check, which returned `ok` from `PRAGMA integrity_check`. It did not execute the application, module workflows, test suite, linter, or package build.

For step 58 the source links of this map were checked against the source at that step, the operating guides' commands were run against a scratch Metaform home, and the whole test suite was run; the build log entry gives the results. No implementation source was changed by the documentation work.

### How to read the evidence

**Author-described functionality** establishes the semantic mechanism and its intended use. **Inspected source** establishes present behavior. **Supplied operational observations** belong to their recorded run. **Derived illustrations** explain a use of the mechanism without claiming a new execution.

A project graph is evidence of a functional representation, not an exhaustive code architecture. The September 26 map's entries can also describe intended functionality with an accompanying finding flagged missing; the current store records the same as a `tbd` work record. A represented node is therefore not, by itself, proof that its producer is implemented; an absent node is not proof that a shared facility is absent.

Relative source links resolve from `docs/inference-metaform/` in the repository. Export and historical-example paths refer to the September 26 source bundle; externally collected report/database paths are identified as such.

<a id="overview"></a>
## 2. Mechanism correspondence at a glance

| Mechanism | Address in the September 26 map | Existing support / implementation boundary |
|---|---|---|
| Functional construction | `code.intake`; internal `document.procedure.intake` and `code.writer.submission` | Served Canonical Intake, recorded one object per call into a building intake layer, read back and proofed, then finished. |
| Type and project naming | Element addresses and `name_length`, join names, namespace prefixes | Computed full/short readings as the element's name; the project's names retained on joins. |
| Reified relationships | Joins and internal subtypes in `code.store.graph` | Independent identities and node-targeted items; a subtype join is a join of type `subtype`. |
| Condition of an object | Findings of that map | Work records, `tbd`, `broken` or `cruft`, apart from the map, on elements and joins. |
| One read of an address | `code.api.map` | `where`: the element, what relies on it, what it relies on, the subtype joins, open work and layers in context. |
| Exact semantic identity | Provider-side `Store.identity` read | Retrieves receiving joins; no semantic equivalence prover or supplied formal resolution mapping. |
| Knowledge selection | Internal `code.resolver.layer` | Starting set, prefix select/mask, hidden-source closure, separate corrections. |
| Scoped inherited knowledge | `Store.context`; properties | Separate applying and visible properties; local items do not inherit. |
| Shared memory | `code.memory.agent` | Nine memory operations over graph nodes; mutable, unversioned memory layer. |
| Prompt versions | Internal `code.store.prompt`; web prompt editor | Version and use records exist; current intake does not populate them. |
| Project-grounded lexicalization | Intended operation described in the reference | Name/address, context, layer, and prompt facilities exist; no shipped lexicalization producer is identified. |
| Blindspot challenge exchange | Internal `code.tracker.challenge`; map answer/approve | State and plan storage exist; producing the critique and coupling prose rationale to state remain separate. |
| Community extension | `code.system.plugin`; `code.chassis` | Module contract, discovery, settings, Context, lifecycle, events, commands/tools, instructions. |
| Artifact realization history | `code.history.variant` | Origin, variant, reconstruction, and extraction operations; separate planned launch/export features are not inferred as implemented. |
| Visual and tool encounters | `code.server.mcp`; `code.gui.web`; `code.interface.command_line` | Shared data operations through different interfaces; the chassis announces each change as `map.changed` and the web GUI pushes it to open pages. |

<a id="records"></a>
## 3. Records, names, relationships, and reads

### Data model

The public `Store` delegates into the data package. The core record definitions and SQLite schema distinguish elements, joins, subtype joins, items, properties, refs, layers, provenance, selections, work records, challenges, plans, and current/correction views. The metaform store's schema is at version 5, and a change to it starts fresh, with no migration; the base, history and prompt databases each keep their own version, 1, so a change to the store's layout refuses none of them.

An element is its identity, its namespace address, its `name_length` and its role, with refs linked to it; its name is its address read through `name_length`. A join identifies its receiver and provider and carries the project's `name` for the functionality, `purpose`, `function`, `ef`, `relation`, `verb`, `observation`, and optional additional fields. A subtype join is a join of type `subtype` held inside a containing purpose join, with its own join id and functional description and no purpose of its own; it names the element it holds, which stays one ordinary element record. Its current row is kept in `current_subtypes`, apart from the `current_joins` every read of the element graph uses, and an element whose only joins are subtype joins is no root and no node of the outer map. An element cannot be moved: its address is its identity, and an element recorded again at an address it held before is the same element, found through `address_elements`, with every record related to it. A join can be moved to another receiver, provider or parent join and keeps its id. A work record, in the `work` table, holds the condition of an element or a join apart from the map, keyed by its own `work_id`, and follows its object through every version.

| Source | Symbols and relevant behavior |
|---|---|
| [records.py](../../src/metaform/data/records.py) | Record types, `Node`, `Element`, `Join`, `Subtype`, the subtype join read with the element it holds, items, properties, `WorkRecord`, `Where`, layer and context results. |
| [schema.py](../../src/metaform/data/schema.py) | Tables and indices for stored records and their relationships. |
| [writes.py](../../src/metaform/data/writes.py) | `add_element`, `add_join`, `add_subtype`; the element's `name_length` and role, the join's name, and dedicated `ef` fields; `edit`, whose `receiver`, `provider` and `parent` move a join. |
| [writes.py](../../src/metaform/data/writes.py) | `add_item` targets a node; `add_property` attaches to an element; `add_work`, `edit_work` and `finish_work` write work records. |
| [names.py](../../src/metaform/data/names.py) | `reading`, `short_name`; reverse segments and expand underscores. |
| [roots.json](../../src/metaform/data/roots.json) | Current five root types as data. |

`short_name` uses the last `name_length` segments. For `code.system.plugin`, length 2 produces `plugin system`, the element's name; the project's name for it, `module contract and loader`, belongs on its join. A missing/false or overlong lookback returns the full reading in the helper. That fallback is implementation behavior, not a semantic judgment that a malformed name is a good type.

### Relationship addressability

`Store.node` groups items at an element or a join, a subtype join included, by their layer. `links_to` finds items linking to a node. `citing` locates records with a matching ref key/value. `where(address, full=False)` is one read of an address: the element, `provides`, every current join it provides with the receiver's purpose, `receives`, every current join it receives, the subtype joins inside each, `held`, the subtype join holding it and the join that subtype join sits in, its open work records, and what the layers in context hold at it; its plain data leaves out ids and empty fields unless `full`. An element held only by subtype joins is no root and no node of the element graph. `children` traverses namespace types rather than pretending every type prefix is a separately instantiated global element.

`Store.identity(element)` returns current joins for which that element is provider, including receiving purposes and EFs. It is useful for examining who receives a capability. Its name does not change its implementation into the exact semantic definition of `C(T)`.

Sources: [Store reads:308-375](../../src/metaform/data/store.py#L308-L375), [reads.where:105-140](../../src/metaform/data/reads.py#L105-L140), [reads.py](../../src/metaform/data/reads.py), and [views.py](../../src/metaform/data/views.py).

### Known Function/Encounter interface difference

The store and intake support `ef` and `verb`, and the map knowledge interface writes them on `add-join` and `add-subtype`; its `edit` and `correct` do not read them. See [C01](#c01) for the exact interface paths. This is a localized correspondence issue, not a missing semantic distinction in the whole record model.

<a id="intake"></a>
## 4. Canonical Intake: resource to stored result

### Operative text

| Resource range | Content |
|---|---|
| [8-23](../../src/metaform/modules/intake/resources/Canonical_Intake.xml#L8-L23) | AUE, Entity, Element, VE, PE, OP, EF, DE, SE, NE, Parametric, and namespace concepts. SE is the Substantial Element. |
| [24-49](../../src/metaform/modules/intake/resources/Canonical_Intake.xml#L24-L49) | Vested-entity rules and photo examples. |
| [50-97](../../src/metaform/modules/intake/resources/Canonical_Intake.xml#L50-L97) | The purpose join type, namespace meaning, reversible readings, valid prefixes, `name_length`, roots, and validity examples. |
| [98-117](../../src/metaform/modules/intake/resources/Canonical_Intake.xml#L98-L117) | Survey, receiving-purpose recursion, closure, annealing, convergence, internal subtypes, recording each object as it is reasoned, and the proofing pass. |
| [118-147](../../src/metaform/modules/intake/resources/Canonical_Intake.xml#L118-L147) | Goal, functional scope, completion, and the response protocol: recording with the intake tools, exact address references, roles, and join fields. |
| [148-176](../../src/metaform/modules/intake/resources/Canonical_Intake.xml#L148-L176) | The XML schema that defines each recorded object's fields, including nested subtype joins. |

The live prompt is not merged with the historical test/old/archive variants. It is the resource loaded by the module when the explicit override is empty.

### Serving

In [intake/__init__.py:35-96](../../src/metaform/modules/intake/__init__.py#L35-L96), `served` loads the resource or selected `intake_file`, substitutes the target's type/value and any `{project_id}`, and appends `footer`. The footer always opens with the author's two sentences, "Do not read past memories or any other details other than the material targeted for intake. Record each element as you work through the process.", then names the intake tools, `intake_absorb` among them, and gives the stop-and-report instruction; project-report and process-feedback requests follow the call's report/debug settings.

The implementation retains exact operative wording through this path. Its optional override is an existing operation, not an encoding implementation. Copy and substitution tests are in [test_intake.py:117-157](../../src/metaform/modules/intake/tests/test_intake.py#L117-L157).

### Recording

`start` opens a building intake layer, or resumes the one being recorded. `element`, `join` and `subtype` each write one object into it through the store's add operations, as the agent reasons it: `element` its address, `name_length` and role, `join` the project's `name` for the functionality with the join's other fields, `subtype` a subtype join inside the parent join `into` with the element it holds. `absorb` makes a recorded join a subtype join inside its parent's join through `Store.edit` with `parent`; `show` reads it back, whole through `Store.layer_graph` or one receiver's joins with `receiver=`; `edit` and `remove` change it in place while it is building, `edit` moving a join by `receiver` or `provider` and never moving an element; `finish` marks it ready and returns the counts, with the open work records on what it recorded as `work`. Every object is named by the key its recording call returned, `element_id` or `join_id`, and an element's address is `namespace_address`. Until then `has_intake()` is false and no context read sees it; the web GUI follows it through `/api/intake-recording` and `/api/layer-graph`.

Each call retains what does not fit, with a notice naming the field: unknown additions go to extra content, a missing field is stored empty, a join end that names no element gets one in the intake layer, and a `name` sent with `element` is kept in the element's extra with a notice that the project's name goes on the join. A subtype join's independently supplied purpose, and an absorbed join's purpose, are preserved in extra rather than silently installed as a second purpose field. The tools carry no condition field; the intake agent writes the condition of an object as a work record with `map_work`.

A repeat intake is recorded in a new Metaform, which becomes active at the finish. Reports are saved at the finish, linked to the layer.

Sources: [recording:115-539](../../src/metaform/modules/intake/__init__.py#L115-L539), [field schemas](../../src/metaform/modules/intake/schema.py).

### The example and source assertions

The September 26 export contains the one stored intake identified above. The [kitchen-timer fixture](../../tests/fixtures/intake_timer.json) is a smaller example of the objects the tests record: a cook receives a countdown function; the timer receives an audible alarm encounter; a tick-loop subtype join is nested inside a join. It is a fixture, not an executed model performance result or an authoritative validation of every semantic placement, and its relations are written as whole sentences.

The intake tests inspect complete writes, names on joins, `ef` and `verb` fields, missing content notices, refs that are not text, duplicate-address handling, second-intake preservation, report linkage and the work count, the absence of a condition field, non-software inputs, override selection, the intentional absence of prompt-store records, and absorbing, receiver-scoped show and edits that never move an element. The relevant cases are listed in [section 14](#tests).

<a id="selection"></a>
## 5. Selection, properties, and visibility

### Resolver behavior

[selection.py:91-156](../../src/metaform/data/selection.py#L91-L156) implements `Resolver`. Its incoming root is an explicit root selection when provided, otherwise nonempty toggled names, otherwise all finished, nonhidden, non-correction layers. An explicitly empty root and an absent root therefore have different meanings.

At each prefix the resolver removes mask rows and adds selectable select rows. When there is no local row for a layer, its incoming membership is preserved. This implements `(incoming & mask) | select` with sparse sets. A descendant select can restore a layer masked by an ancestor, without selecting the parent or a sibling.

[hidden_closure](../../src/metaform/data/selection.py#L56-L71) repeatedly adds layers whose recorded sources intersect the hidden set. That transitive closure is specific to `layer_sources`; it is not a blanket inference that any semantically associated layer is invalid. Building layers are excluded. Finished corrections participate through their separate application rules.

### Views

[reads.context:257-291](../../src/metaform/data/reads.py#L257-L291) returns `applying` properties on the prefix chain and `visible` properties on descendants. A property encountered during ancestor inspection retains the attachment scope at which it was resolved. Local item reads are separate.

The [C++/Bash source test](../../tests/test_store_layers.py#L286-L329) establishes the intended distinction in its assertions: both properties are visible at `code`, neither applies there, and a language property on one branch does not apply to another. A separate test shows an item staying local while a property stays with its element, which never moves.

Direct named `layer_items` can inspect hidden or masked content unless `in_context=True` is requested. Raw reads explicitly widen the view. Therefore comments describing universal exclusion must be read together with each public operation's view controls. Selection governs context, not deletion or a security boundary. See [Store.layer_items](../../src/metaform/data/store.py#L343-L352).

### Source-specific implication

This is implemented support for scope-sensitive knowledge and the author's Encounter propagation account. It does not, by itself, construct a language Encounter or infer all of its consequences. The producing inference operation remains distinct from the storage and view mechanics.

<a id="memory"></a>
## 6. Memory

`code.memory.agent`, named `memory module`, maps to [modules/memory/__init__.py](../../src/metaform/modules/memory/__init__.py). `_memory` finds the layer by kind or creates a ready, mutable, hideable `memory` layer on first write. [Layer creation](../../src/metaform/data/layering.py#L96-L111) deliberately skips provenance for memory.

An observation is an item at a node; a relation is an item at its from-node with a link to its to-node. Joins, subtype joins included, use ids; elements can use addresses or ids. `open_nodes` presents related memory, while `read_graph` requests the memory layer in context. The mutation helper `_at` deliberately reads the layer directly to change its items.

The nine operations are declared as module verbs and become MCP tools through the common module contract. `create_entities` can create an element in the memory layer. `delete_entities` removes memory items at requested nodes, not their underlying map identities.

[update_item and delete_item](../../src/metaform/data/writes.py#L408-L426) modify/remove memory in place. Memory has no own edit history in this source. Claims that every memory is immutable, versioned, or provenance-linked would therefore misstate the implementation.

Inspected tests include [join-addressed memory](../../src/metaform/modules/memory/tests/test_memory.py#L57-L63), [deletion semantics](../../src/metaform/modules/memory/tests/test_memory.py#L77-L88), and [selection](../../src/metaform/modules/memory/tests/test_memory.py#L121-L130). The September 26 export holds no memory observations.

<a id="corrections"></a>
## 7. Corrections and re-examination

The September 26 map holds `code.stack.correction` as an internal contribution of the graph store to the chassis. Implementation is in [corrections.py](../../src/metaform/data/corrections.py), [layering.py:244-355](../../src/metaform/data/layering.py#L244-L355), and the `Store.correct`, `finish`, `peel`, `history`, and `peel_preview` APIs.

A correction is assembled while building and applied when finished. Current records are recomputed against the applied stack. The top correction can be peeled, returning it to building and recomputing affected current views. Correction layers are not normal selectable/hideable knowledge layers.

An element cannot be moved: a correction's `address` for an element is not applied and is named in a notice. A join can be moved: a correction's `receiver`, `provider` or `parent` is a change of the same join, which keeps its id and everything attached to it; with `parent` it becomes a subtype join, and the subtype joins it held pass to its new parent. A correction layer that removes a thing orphans everything current that still depends on it and names each in its result; nothing is refused. An element recorded again at the same address is the same element, so what was attached to it returns with it. The peel preview names a join a layer moved and where it moves back to.

The source marks layers built from the original adding layer for re-examination when the relevant correction applies. It does not implement an unspecified universal transitive semantic invalidation algorithm. The hidden-layer source closure and correction re-examination are different mechanisms.

A further lifecycle detail matters for ordinary knowledge: `writes.unchangeable` protects a finished intake and finished corrections and redirects memory to its own mutation APIs. Ordinary knowledge records can be edited in place, including after finish; this guard does not treat their declared `mutable` value as a universal immutability switch. See [writes.py:431-439](../../src/metaform/data/writes.py#L431-L439), [edit:590-629](../../src/metaform/data/writes.py#L590-L629), and [the finished-layer test](../../tests/test_store_layers.py#L241-L257).

Inspected correction tests cover precedence, history, peeling, orphan/restoration, join moves, the element that never moves, re-examination, and retention of `ef`: [test_store_corrections.py](../../tests/test_store_corrections.py).

<a id="prompts"></a>
## 8. Prompt versions and lexicalization

### Existing prompt facilities

The internal project address is `code.store.prompt`; its source is [data/prompts.py](../../src/metaform/data/prompts.py).

`add_prompt` creates a prompt and version 1. `add_prompt_version` creates a parent-linked next version, or returns the parent with a notice for identical text. `shipped` supports a shipped prompt's evolution while retaining a saved edit. `record_use` links a version to a project, Metaform, and layer. Reads expose versions and the layers associated with a version.

The web prompt editor uses these facilities. The existence of the editor and APIs is independent of whether the supplied home currently has prompt records.

### Current intake usage

The intake's provenance explicitly stores `prompt=None`; it does not call the version store to preserve the served text. The bundle identifies no populated prompt store, and the intake tests explicitly assert that serving the resource creates no stored prompt version. See [intake provenance](../../src/metaform/modules/intake/__init__.py#L179-L195) and [tests:541-580](../../src/metaform/modules/intake/tests/test_intake.py#L541-L580).

### Intended lexicalization producer

The author-described operation is fully defined in [REFERENCE.md](REFERENCE.md#lexicalization): infer referents against the project, substitute recorded project names without paraphrase, attach canonical-term-to-namespace mappings and knowledge directions, identify any selected imperative contribution, and stop before execution.

The source supplies the useful ingredients: names and addresses, relationship reads, node memory, layer selection, prompt versions, Context, module tools, and instructions. No shipped module performs that task-specific preprocessing as a lexicalization producer. Prompt versioning is not lexicalization, and composing module-purpose instructions is not the same operation.

No current before/after lexicalized prompt pairs were supplied. The reference's pair uses a real project name but is marked as a derived illustration. Original pairs and their selected knowledge are a collection target, not a precondition for describing the intended operation.

<a id="challenges"></a>
## 9. Blindspot challenges and plans

The September 26 map represents `code.tracker.challenge` inside the graph store's receiving relationship with the chassis. The state implementation is [data/challenges.py](../../src/metaform/data/challenges.py), exposed through [map answer/approve](../../src/metaform/modules/map/__init__.py#L200-L206) and Store operations.

`answer` stores a state in `A`, `B`, or `C`, optional C target, and timestamp, associated with a critic item. A C without a link is retained with a notice. Unsupported answer words are handled as specified by the operation; `plan` is not an agent answer that directly substitutes for approval.

`approve` operates on B and updates the disposition to plan. It can create a plan row when the challenge item targets an element added by the critic's layer. The exposed approval verb is CLI-only. Separately, `add_plan` creates a plan directly without a challenge approval. The source's header comment saying a plan comes only from approval is narrower than the actual public operations; the direct operation is implemented and tested.

The answer API has no prose-rationale parameter. Its state table therefore is not the complete conceptual blindspot answer. A substantive response includes reasons, unexplored relevance, or where and how functionality is already supplied. Existing items/layers can store those explanations, but the snapshot does not demonstrate a producer automatically writing a prose answer alongside its disposition.

The shipped modules include no independent blindspot-producing workflow. That producer boundary does not remove the implemented challenge tracker or shared inference/module facilities. A critic can also record each gap it finds as a work record on the object it concerns, apart from the map. The September 26 export contains no challenge states or plans.

Source assertions: [state/link behavior](../../tests/test_store_challenges.py#L24-L39), [approval and critic-layer preservation](../../tests/test_store_challenges.py#L42-L57), and [direct planning](../../tests/test_store_challenges.py#L60-L71).

<a id="extensions"></a>
## 10. Community extension and execution facilities

### One contract, several receiving purposes

In the September 26 map, `code.system.plugin`, named `module contract and loader`, is supplied to module authors, the chassis, CLI, MCP, builder, and agent instructions. Its two internal module-author examples are `code.template.module` and `code.module.example`.

| Capability | Concrete implementation |
|---|---|
| Module declaration | [Module, Verb, Noun, Subscription, Status](../../src/metaform/module.py#L67-L150). |
| Per-call context | [Context](../../src/metaform/module.py#L153-L200), [context.build](../../src/metaform/context.py). |
| Settings declaration and resolution | [settings.py](../../src/metaform/settings.py), module-owned registrations in loader. |
| Discovery | [loader._candidates and discover](../../src/metaform/loader.py#L56-L186): system, user-home, entry points. |
| Metadata before import | [module_metadata.py](../../src/metaform/module_metadata.py): literal metadata inspection. |
| Task ownership | [loader.spawn and task completion](../../src/metaform/loader.py#L198-L228), unload/reload/shutdown paths. |
| Shared store | `Context.require_store` and [Store](../../src/metaform/data/store.py). |
| Command surface | [cli.py](../../src/metaform/cli.py), [grammar.py](../../src/metaform/grammar.py). |
| MCP tool surface | [MCP server](../../src/metaform/modules/mcp/server.py). |
| Agent instructions | [instructions.compose](../../src/metaform/instructions.py#L51-L66). |
| Change announcement | [changes.py](../../src/metaform/changes.py): the store and the home note what a command changed, and the chassis fires `map.changed` once per metaform changed when the command ends. |
| Empty template | [template](../../src/metaform/modules/template/__init__.py). |
| Working demonstration | [helloworld](../../src/metaform/modules/helloworld/__init__.py). |

Metadata can be read from recognized literal declarations, including the reader's supported `manifest.py` fallback; the shipped template uses `__init__.py`. This is a description of source compatibility, not a new requirement to add manifests.

The loader records disabled, incompatible, missing-dependency, and failed candidates separately. Its module id precedence is determined by discovery order. Import registers settings under module ownership; unload withdraws owned registrations and tasks while leaving stored data. The source includes both synchronous and asynchronous lifecycle paths; owned coroutines require an available running loop when spawned.

### Shipped modules

| Module | Function in this source | Shipped default |
|---|---|---|
| `intake` | Serve the Canonical Intake, record it one object per call while it builds, anneal, show, edit and finish it, report intake state. | Enabled |
| `map` | Graph reads, the one read of an address, knowledge and correction operations, work records, selection, challenges/plans. | Enabled |
| `memory` | Shared observations and relations at map nodes. | Enabled |
| `mcp` | Serve the generated tool surface over stdio. | Enabled |
| `web` | Detached graph and record inspection interface, pushed each change to the map, with Clear project. | Enabled |
| `helloworld` | Exercise the public module contract and shared capabilities. | Disabled |
| `template` | Empty module starting point. | Disabled |

These are declaration defaults, subject to persisted enablement and environment compatibility. The availability of a chassis facility is not proportional to how many current modules call it.

### CLI/MCP and instructions

The MCP server derives schemas from verbs, nouns, relevant settings, and operation-specific controls. It creates a Context, awaits coroutine verbs, and offloads plain verbs to a worker thread. Its tool list is rebuilt on requests. The server's instruction text is composed when constructing the server; it is not rebuilt merely because a tool-list request occurs.

Consequently, a module or surface change can affect subsequent tool lists while an already connected host retains the instruction text supplied at initialization until reconnection. See [server.py:329-417](../../src/metaform/modules/mcp/server.py#L329-L417) and [instructions.py](../../src/metaform/instructions.py). After each tool call the server announces what the call changed, as the command line does when a command ends.

<a id="events"></a>
## 11. Event delivery and the earlier illustration

The September 26 map places `code.bus.event` inside the join where the plugin system serves the chassis. Current source is [events.py](../../src/metaform/events.py), exposed through `Context.publish` and `Context.publish_async`; task creation is separately exposed through `Context.spawn`.

`publish` iterates matching loaded subscriptions, builds the receiver's Context, deep-copies the payload, and calls the handler before moving on. `publish_async` likewise processes each matching subscription, awaiting coroutine handlers or awaiting `asyncio.to_thread` for a plain handler. Both report per-subscriber outcomes. In the async path, cancellation of the publisher task is re-raised rather than merely converted into one subscriber result.

The chassis publishes one topic itself: `map.changed`, `{project, metaform_id}`, fired through the same `publish` once for each metaform a command changed, when the command ends on the command line and after each MCP tool call, from [changes.py](../../src/metaform/changes.py). The web module's subscriber hands it to the running server, which pushes it to every open page. After the page's own writes that changed the map, the web server calls the same `changes.announce` with the surface `web`, so a subscriber hears a clear made on the page as it hears one from the command line.

This establishes individual attribution and isolation of reported subscriber failures. It also establishes that the publication call waits for its sequence of deliveries. Offloading synchronous work preserves event-loop availability; it does not mean the publisher returns before delivery, or that an arbitrary coroutine cannot block internally.

The author's earlier `code.bus.data.event -> code.runtime.execution` example described an illustrative purpose of attributable work that does not block the publisher or another module. It is not a literal inventory of the current source. The September 26 map's different names, or absence of a separately named runtime node, do not prove any scheduling architecture. The distinction is established by inspecting the actual delivery and task code.

Relevant source assertions are in [test_base.py](../../tests/test_base.py), including individual outcomes and a running loop during awaited delivery, and [test_lifecycle.py](../../tests/test_lifecycle.py), including owned-task cancellation before stop. These are inspected assertions, not newly executed results.

<a id="supporting"></a>
## 12. Other implemented project capabilities

### Project registration and storage context

[home.py](../../src/metaform/home.py), [context.py](../../src/metaform/context.py), and [data/session.py](../../src/metaform/data/session.py) provide project registration, Metaform selection, and store access through the Metaform home. The current source uses `~/.metaform` or `METAFORM_HOME` for its state; a project's artifact path identifies what it examines rather than a requirement to place runtime state inside that project.

A per-call project or layer choice and a stored folder setting are separate inputs. Context construction resolves those inputs for the operation. This is part of supplying the same functional map through different host environments.

### Read and write encounters

`code.api.map` connects Store operations to verbs and tools. Its reads cover entry roots, the one read of an address, elements, receiving/provider joins, identity, subtypes, children, node content, property context, links, refs, history, stack, search, layers, and work records. Knowledge operations create and populate layers, write records and plans, and manage corrections; `work` adds, edits, lists and finishes work records. Nothing is refused for its content: only a field a record cannot be stored without stops a call, and every other missing field is stored empty with a notice. Selection and challenge operations are additional explicit verbs.

`code.gui.web` supplies graph and record inspection over these stored operations. [server.py](../../src/metaform/modules/web/server.py) exposes named reads and four writes: apply layers to the project folder, save a prompt version, peel/discard the top correction, and clear the selected project through the same `clear_project` that `metaform clear project --confirm` calls, with its caution read first from `/api/clear-preview`. After a write that changed the map it fires `map.changed` on the module event bus, as a command does. It holds one server-sent events stream per open page and writes each `map.changed` to all of them; its loop waits for a connection with no timeout, and nothing in it polls. [app.js](../../src/metaform/modules/web/page/app.js) and the page resources render the functional graph, purpose relationships, inspector, and prompt editing. They do not imply that every possible graph edit is a browser operation.

The graph view's purpose vertices make the receiving relationship visible rather than drawing only an unlabeled dependency. The stored graph's own internal subtype decomposition should still be distinguished from a code-module architecture diagram.

### Origins and variants

[history.py](../../src/metaform/data/history.py) implements repository/plain-folder boundaries, origin creation, collecting variants against a selected origin, reconstructing their files, and extraction. Variants are stored relative to their origin rather than forming an implicit chain of unrelated worker deltas. Reconstruction checks recorded file hashes.

The repository boundary includes tracked files and untracked, nonignored files. The original intake report warns that the examined working tree contained substantial untracked historical material. That warning is a recorded observation of that run, not a newly measured inventory of the user's present checkout.

The September 26 map separately names intended side-by-side web-variant launching and origin-unit wheel export/import. Those features carry findings flagged missing there; ordinary variant reconstruction must not be described as proof they are complete. See [C10](#c10).

### Exchange, reports, build, and installation

| Project function | Source and current role |
|---|---|
| Graph export/import | [data/exchange.py](../../src/metaform/data/exchange.py): exchange of graph records, layers and work records, with identity, dependency, and conflict handling; a document at another schema version is refused. This is distinct from origin-unit wheel exchange. |
| Feedback and reports | [reports.py](../../src/metaform/reports.py), [Store report methods](../../src/metaform/data/store.py#L460-L475): retain project reports, process feedback, and shapes and associate available records with layers/runs. |
| Wheel construction | [build.py](../../src/metaform/build.py): build from loaded modules and declared dependencies, omit module tests, support pure-Python vendoring and directly runnable wheel packaging. |
| Host installation | [install.py](../../src/metaform/install.py): supported host registration, skill placement, recorded changes and backups, and removal of those changes. |
| Registered-server probe | [probe.py](../../src/metaform/probe.py): start the command being registered and check initialization/tool listing, then stop it. This is not the separate per-host skill-loading proof. |
| Test/CI functionality | [checks.yml](../../.github/workflows/checks.yml), [conftest.py](../../conftest.py), and tests: source definitions of cross-platform checks, fixtures, and execution assertions. |

<a id="correspondence"></a>
## 13. Localized correspondence issues

These entries preserve both the described semantics and the supplied source. They do not silently revise either one, and no code fixes were made as part of the documentation.

<a id="c01"></a>
### C01. The map knowledge interface cannot change a join's `ef` or `verb`

**Source-inspected.** Intake and Store support `ef` and `verb` on joins and subtype joins. The map module's `op=add-join` and `op=add-subtype` read both and write them to the dedicated fields. Its `FIELDS`, which `op=edit` and `op=correct` read, omit them: a value given there is named in a notice, `op=edit does not read ef; it was ignored.`, and nothing is written for it. `intake edit` changes both while an intake is building, and `Store.edit` and `Store.correct` take both.

Sources: [map fields](../../src/metaform/modules/map/__init__.py#L27-L28), [operation reads and dispatch](../../src/metaform/modules/map/__init__.py#L239-L384), [intake recording](../../src/metaform/modules/intake/__init__.py#L287-L318), [Store add methods](../../src/metaform/data/store.py#L185-L218), [editable fields](../../src/metaform/data/rows.py#L25-L31).

**Correspondence:** preserve Function/Encounter in the design and record model. The source-local repair area is the map interface's edit and correct, not removal or reinterpretation of the distinction.

<a id="c02"></a>
### C02. One live language-intake exclusion and the broader Encounter account coexist

**Literal operative text plus author-described mechanism.** The live [line 93](../../src/metaform/modules/intake/resources/Canonical_Intake.xml#L93) says:

```xml
<example namespace_address="code.cpp" valid="false" reason="this is language" />
```

The author's broader account attaches language Encounters such as `code.c` and allows `code.html` as a language Encounter, while rejecting encoding alone as a functional subtype. The property tests separately demonstrate scoped language-property application and visibility.

**Correspondence:** the supplied implementation does not specify a complete producer workflow connecting the functional intake-stage exclusion to subsequent language-Encounter attachment and inference. Neither changing the live example nor deleting language Encounters from the reference would establish that missing correspondence. The reference describes the mechanism; this entry preserves the exact source boundary.

<a id="c03"></a>
### C03. A broad stored provider and the single-EF semantic Type are different levels of description

**Author definition plus literal source representation.** The exact identity definition uses one `e` per semantic Type at its represented resolution. The intake's EF definition at [line 18](../../src/metaform/modules/intake/resources/Canonical_Intake.xml#L18) says that a PE type on the whole can serve different VEs through different Encounter Functions, each recorded in its receiving join. Stored providers accordingly have several receiver-specific descriptions.

**Correspondence:** no complete formal mapping from those broad provider records to the resolution-specific Type is supplied. `Store.identity` retrieves those relationships; it does not resolve the semantic correspondence by proving equivalence. The exact definition is retained without inventing a canonicalization rule, subtype split, or runtime approval mechanism.

<a id="c04"></a>
### C04. Challenge state does not itself store the substantive answer

**Source-inspected.** `answer` takes item, state, and optional link. The resulting state record has no explanation field. The conceptual challenge requires the project's reasoning.

**Correspondence:** item and layer facilities can hold that explanation, but automatic coupling to the state operation is not demonstrated. The existing B approval and direct-plan routes remain as implemented; neither is made into a new general gate on inference. See [section 9](#challenges).

<a id="c05"></a>
### C05. Lexicalization and criticism producers are not replaced by their supporting facilities

**Source inventory and author account.** The source ships the seven modules listed above. It contains names, layers, prompts, context, memory, and challenge states but no identified shipped producer for project-grounded prompt lexicalization or the full critic/challenge exchange.

**Correspondence:** describe those intended operations from the author's explanations and their support from source. Do not label the prompt store a lexicalizer, the challenge tracker a critic, or the absence of either producer an absence of community extension.

<a id="c06"></a>
### C06. Retention, editability, and participation have distinct implementations

**Source-inspected.** Memory is mutable and unversioned; ordinary knowledge records can be edited in place; intake and finished corrections are protected by different rules; prompt versions retain text immutably. Hiding and masking exclude context without deleting content, and explicit named/raw reads can inspect retained content.

**Correspondence:** descriptions such as every layer is immutable, every memory has provenance, or every hidden item is inaccessible through all reads would be incorrect. The exact layer lifecycle is the basis for explaining reuse and history. See [sections 5-8](#selection).

<a id="c07"></a>
### C07. Intake preservation is implemented; encoding is an author intention without a selected mechanism

**Source-inspected and author-described.** Exact resource text, controlled substitutions, copy tests, and an explicit override exist. No encoding, encryption, obfuscation, or decoding service is specified in this soupshot.

**Correspondence:** preserving operative behavior on release does not justify inventing a secrecy scheme or asserting that the intake will never be published. The full operative material is appropriate to this internal reference.

<a id="c08"></a>
### C08. The XML schema defines the fields; the tools record one object per call

**Source-inspected.** The resource's response protocol says to record each object with the intake tools as it is reasoned; its XML schema defines each object's fields and is not returned as a document. The module never parses XML.

**Correspondence:** the agent performing the intake fills each tool's fields. The resource is a model-directed procedure; recording and structural notices do not amount to deterministic semantic execution of the intake. See [section 4](#intake).

<a id="c09"></a>
### C09. The resource's role prose and schema differ on `AUE`

**Literal resource and the September 26 export.** The response prose says an inside element has one role among `DE`, `SE`, and `NE`, while an outside VE has `VE`. The illustrative outer element schema at [line 152](../../src/metaform/modules/intake/resources/Canonical_Intake.xml#L152) also includes `AUE`. The September 26 map uses `AUE` for `code.graph.knowledge` and `DE` for `code.chassis`.

**Correspondence:** this is recorded as a local role-schema distinction requiring alignment, rather than silently expanding the role prose or rewriting the export. It does not change the Entity/Element or receiver/provider semantics.

<a id="c10"></a>
### C10. The September 26 map includes three intended features with missing findings

**Supplied graph observations, with current source boundaries.**

| Represented contribution | Recorded intended function | Status relevant to this documentation |
|---|---|---|
| `code.launcher.variant` | Serve web variants on separate ports for side-by-side inspection. | Marked missing in that graph and its report; existing history extraction is not this launcher. |
| `code.export.origin` | Export/import a complete origin unit as a reconstructable wheel. | Marked missing; current graph-data exchange and ordinary package building are different capabilities. |
| `code.verifier.skill` | Verify that each host actually loads the skill from the installed folder. | Marked missing; successful MCP server probing does not perform that host-specific skill check. |

The source at step 58 still has no implementation of these producers. Their functional descriptions can remain in a graph as intended contributions; the current store records such a contribution as a `tbd` work record. Their implementation must not be inferred from a broad neighboring capability.

<a id="c11"></a>
### C11. Reported test and lint results are historical run observations

The September 26 intake report records `482 passed` for pytest, strict pyright with zero errors, and 117 Ruff findings. The corresponding graph flags CI lint as broken. These are supplied results from that intake run, not tests or lint executed for this reference. They are kept as available operational evidence without certifying the current checkout; the build log records each later step's own results.

<a id="c12"></a>
### C12. The resource's schema shows a name on the element; the store keeps names on joins

**Literal resource and current store.** The resource's schema shows `<name/>` on each element, the outer one at [line 154](../../src/metaform/modules/intake/resources/Canonical_Intake.xml#L154) and the one a subtype join holds at [line 164](../../src/metaform/modules/intake/resources/Canonical_Intake.xml#L164). The store holds an element as its address, `name_length` and role, and the project's name for a functionality as the join's `name`, MAP-020. `intake element` keeps a `name` given to it in the element's extra, with a notice that the project's name goes on the join with `intake join name`, and the tool's own description of `name` says the same.

**Correspondence:** the resource's wording is the author's and is not edited by the build; the tools keep what an agent following it sends and direct the name to the join.

<a id="c13"></a>
### C13. The resource says to remove absorbed subparts; the tools anneal by moving the join

**Literal resource and current tools.** The response protocol at [line 141](../../src/metaform/modules/intake/resources/Canonical_Intake.xml#L141) tells the agent not to leave absorbed subparts recorded as independent root elements, to remove them, and to keep them as subtype joins inside the parent's matching purpose join. The tools anneal with `intake absorb`, which makes the join where the element provides a subtype join inside the parent's join, keeping its id and every field. The element stays one element record and, held only by subtype joins, is no root. An element removed after it was absorbed leaves its subtype join naming an element that is gone, and the notice names it. The schema's nested join also carries a provider beside its inline element, with no `type` and no `non_goal`.

**Correspondence:** the resource's wording is the author's; the tools implement annealing as join moves, MAP-030, and name what an agent's removal leaves behind.

### Event scheduling and instruction refresh

The earlier bus/runtime illustration versus current sequential awaited delivery is explained in [section 11](#events). Request-time tool-list regeneration versus server-construction instruction composition is explained in [section 10](#extensions). Both are established from code rather than inferred from graph naming.

<a id="tests"></a>
## 14. Tests and available operational evidence

### Inspected source assertions

| Mechanism | Test source and representative cases |
|---|---|
| Intake integrity | [test_intake.py:117-157](../../src/metaform/modules/intake/tests/test_intake.py#L117-L157): byte copies, target-only substitution, footer settings. |
| Intake field retention | [test_intake.py:160-417](../../src/metaform/modules/intake/tests/test_intake.py#L160-L417): recorded object by object and read back whole, names on joins and an element's name kept in its extra, `ef`, `verb`, missing fields, extra content, refs that are not text. |
| Repeated intake and non-code artifacts | [test_intake.py:420-538](../../src/metaform/modules/intake/tests/test_intake.py#L420-L538): new active Metaform, report and feedback with the work count, no condition field, duplicate addresses, status, non-software fixture. |
| No implicit prompt version | [test_intake.py:541-580](../../src/metaform/modules/intake/tests/test_intake.py#L541-L580). |
| Recording while building | [test_intake.py:583-792](../../src/metaform/modules/intake/tests/test_intake.py#L583-L792): unseen by context reads until the finish, read back, edited and removed while building, started by a first record, resumed, recorded and proofed per the resource, absorbed, shown one receiver at a time, named by the key each call returned, and edited without moving an element. |
| Local selection and inheritance | [test_store_layers.py:139-173](../../tests/test_store_layers.py#L139-L173), [286-329](../../tests/test_store_layers.py#L286-L329), [349-400](../../tests/test_store_layers.py#L349-L400). The select test is named `test_a_select_toward_the_leaves_from_a_mask_turns_the_layer_on_again_there_and_nowhere_toward_the_trunk`, naming the direction by the tree's parts. |
| Knowledge and memory lifecycle | [test_store_layers.py:122-136](../../tests/test_store_layers.py#L122-L136), [227-257](../../tests/test_store_layers.py#L227-L257). |
| Relationship-addressed memory | [memory tests](../../src/metaform/modules/memory/tests/test_memory.py): join nodes, relations at both ends, deletion, selection, and newly noted elements. |
| Challenges and direct plans | [test_store_challenges.py](../../tests/test_store_challenges.py). |
| Corrections | [test_store_corrections.py](../../tests/test_store_corrections.py): precedence, peel, orphans, join moves, the element that never moves, re-examination, and `ef`. |
| Elements, joins, work records and the address read | [test_store_map.py](../../tests/test_store_map.py), [test_store_reads.py](../../tests/test_store_reads.py), [test_store_operations.py](../../tests/test_store_operations.py): an element is its address, `name_length` and role, names on joins, subtype joins, identity kept at an address, work records apart from the map, and `where`. |
| Announcing changes | [test_map_changed.py](../../tests/test_map_changed.py): `map.changed` once per command that changed the map, never for a read, on the command line and over MCP. |
| Prompt version/use | [test_prompts.py](../../tests/test_prompts.py): version retention, use linkage, shipped text, indexed reads. |
| Module lifecycle | [test_lifecycle.py](../../tests/test_lifecycle.py): spawned task completion before stop, unload/reload, settings restoration, dependency failure. |
| Event outcomes and async loop | [test_base.py](../../tests/test_base.py). |
| Module contract examples | [helloworld tests](../../src/metaform/modules/helloworld/tests/test_helloworld.py), [template tests](../../src/metaform/modules/template/tests/test_template.py). |
| MCP and web interfaces | [MCP tests](../../src/metaform/modules/mcp/tests/test_mcp.py), [web tests](../../src/metaform/modules/web/tests/test_web.py): tools read as the command line reads, the page pushed without polling, work states drawn, Clear project. |
| Variant history and exchange | [test_history.py](../../tests/test_history.py), [test_store_exchange.py](../../tests/test_store_exchange.py). |

These tests show expected operation and available coverage in source. A passing result is reported only where an operational record reports it: the September 26 run's report, and each build step's entry in the build log.

### Available run material

The September 26 run's report and feedback are in the supplied bundle under:

```text
external/metaform-home/projects/metaform/reports/
  2f6b86ffc49c4575bfdbf0ad2ac712f7-report.md
  2f6b86ffc49c4575bfdbf0ad2ac712f7-feedback.md
```

The earlier run has report/feedback files with id `70618d7651c24ba9b04219544af156d8`, but no retained export of its withdrawn Metaform. Historical intake outputs and the address-only/knowledge-layer examples are catalogued in [EXAMPLES_TO_COLLECT.md](EXAMPLES_TO_COLLECT.md#available). Their source roles are not merged with the current run.

<a id="graph-index"></a>
## 15. Complete index of the September 26 map

The following index is derived from the supplied `exports/metaform-main.json`, not from an invented decomposition of the code. It includes all 19 global elements, all 33 purpose joins, and all 26 internal subtypes in that export. It is an index to the functionality represented on September 26; implementation status remains governed by the sections above. The project names in these tables are the export's descriptor names at its elements and the names on its subtype rows; the current store holds a project name on the join, and a subtype as a join of type `subtype` holding an element.

`document.specification` and the internal `document.rules.collaboration` are included because the supplied map represents them. The excluded narrative documents themselves were not used as a source for this reference.

### Global elements

<!-- Generated from the September 26 project export. -->
| Functional address | Project name | Role |
|---|---|---|
| `stakeholder.orchestrator.agent` | agent orchestrator | VE |
| `stakeholder.author.module` | module author | VE |
| `code.graph.knowledge` | Metaform | AUE |
| `code.chassis` | chassis | DE |
| `code.store.graph` | data access object and metaform store | SE |
| `code.interface.command_line` | metaform command line | SE |
| `code.system.plugin` | module contract and loader | SE |
| `code.intake` | intake module | SE |
| `code.api.map` | map module | SE |
| `code.memory.agent` | memory module | SE |
| `code.server.mcp` | MCP module | SE |
| `code.gui.web` | web GUI | SE |
| `code.history.variant` | origins and variants | SE |
| `code.installer` | installer | SE |
| `code.builder.package` | metaform build | SE |
| `code.channel.feedback` | feedback and reports | SE |
| `document.instructions.agent` | agent instructions | SE |
| `document.specification` | Metaform specification | NE |
| `code.suite.test` | tests and CI | SE |

### Purpose joins, grouped by receiver

Each entry names the receiving entity first, then the provider, followed by the stored receiving purpose. These are literal purposes from the export. The full join id keeps the relationship addressable independently of its endpoints. Function, `ef`, relation, observation, refs, and additional fields remain in the export; this index does not collapse them into the purpose text.

#### Receiver: `stakeholder.orchestrator.agent`

**Provider: `code.graph.knowledge`**  
Join: `69d73555e9dc4355b32528f3c061a83d`

Have every agent it hands work on a project start from that project's functional form, what each part is for, who receives it and how, instead of reconstructing it from the files each session.

**Provider: `code.chassis`**  
Join: `1e00bc6690ca49f5aad029dcd6f0ec4b`

Give each agent its project's map, its place in it and exactly the knowledge in scope for its task, from whatever folder and AI tool the agent works in.

**Provider: `code.intake`**  
Join: `18b253a243e34988a4209e60c4c69036`

Have a subagent map the project's functionality once, from the artifact itself, and keep that map whole as the base every later layer builds on.

**Provider: `code.api.map`**  
Join: `d04ee1f8cbef49219241200a41b976ba`

Have agents read the purpose of a part before they change it, and record what they learn as knowledge and correction layers on the same map.

**Provider: `code.memory.agent`**  
Join: `c7fa6058b9424e609ada2b4350110e9e`

When the map is wrong or incomplete at a place, have the agent that finds out leave a note there, so the next agent reads it where it looks.

**Provider: `code.server.mcp`**  
Join: `650c3813fcd8445180a99d5d72871831`

Let agents in any AI tool reach every Metaform command as a tool, with the same checks and the same next steps as the command line.

**Provider: `code.gui.web`**  
Join: `dc3061a3050a4b81b626b226b5c79ecc`

See each project's functional map, its layers, provenance, prompts and corrections in a browser, and change only what the orchestrator chooses to change there.

**Provider: `code.history.variant`**  
Join: `86fa0bfb605a4a679e54fd809e840c6e`

Collect each worker's output, committed or not, against one baseline, and rebuild any of those outputs later, anywhere.

**Provider: `code.installer`**  
Join: `00ab16578835436eace9173f192d2864`

Have every AI tool its agents run in start Metaform's server and find its skill, proven before setup says it is done, and removable again without touching anything else.

**Provider: `code.builder.package`**  
Join: `19b99a8429c54e0e932d12b43836b677`

Run Metaform with exactly the modules it has enabled from one file, on a machine or in a hosted code environment with nothing installed, and keep that run's data apart until it is pulled in.

**Provider: `code.channel.feedback`**  
Join: `654c2282eef94b5daf46ad3be00330cb`

Have an agent that cannot continue stop and leave what it has with a trouble report instead of retrying, and keep every intake's report and process feedback beside the layer it made for review.

**Provider: `document.instructions.agent`**  
Join: `c3ca5aea31b544adb4304e78ea00e971`

Have every agent that enters a project learn what Metaform keeps there, what each enabled module is for, and the one next step, such as delegating the intake, without anyone briefing it.

**Provider: `document.specification`**  
Join: `fd34edf581314229ba537ce99136bf46`

Hand every agent building Metaform one current contract to build from, with the reason for each requirement and the tests that protect it, so the build serves the design and not an agent's guess.


#### Receiver: `stakeholder.author.module`

**Provider: `code.system.plugin`**  
Join: `d14bd3498b614dfbaf0754c99b28dba3`

Add a capability to Metaform as a module, declared once in its own folder, that runs as a metaform command and an MCP tool with its own settings, events, status line and lifecycle, without changing the chassis.

**Provider: `code.builder.package`**  
Join: `01349d91d1e84635b374fcbd34ae1729`

Ship the module to others inside a Metaform wheel with the dependencies it declares.


#### Receiver: `code.chassis`

**Provider: `code.store.graph`**  
Join: `a4411d11810741edafd75313350a8283`

Keep every registered project's metaforms in the Metaform home, never in a project folder, and let modules reach them only through one door that applies the same visibility rules on every read.

**Provider: `code.interface.command_line`**  
Join: `61ce3031fa784b4c8c69043e53bf1b0d`

Run every chassis command and module verb the same way, with every switch a setting declared once, help drawn from the live declarations, and every error ending in the one command to run next.

**Provider: `code.system.plugin`**  
Join: `2ae83edea21e46da9a41e5b539480df6`

Carry every capability beyond its own commands as modules it finds, checks and loads on its own, and withdraw everything a module registered when it goes.


#### Receiver: `code.interface.command_line`

**Provider: `code.system.plugin`**  
Join: `13e8850ca5da495392d925ee620e5b46`

Parse and run each module verb from its one declaration, with the settings it reads as its switches and its help page drawn from that declaration.


#### Receiver: `code.intake`

**Provider: `code.store.graph`**  
Join: `ec77c8b8bd474c9cab93ca57700992dd`

Store the whole submission as one intake layer that nothing edits afterward, and never lose an earlier intake.

**Provider: `code.channel.feedback`**  
Join: `d92b9a5241b24b4683f60b2128f4ca3b`

Keep the intake agent's report on the project and its process feedback as provenance of the intake layer.


#### Receiver: `code.api.map`

**Provider: `code.store.graph`**  
Join: `2556a464e1a14be680970d8ad518831a`

Answer every map verb with exactly one data access object operation, so an agent reads what the store's rules let it see and writes only through them.


#### Receiver: `code.memory.agent`

**Provider: `code.store.graph`**  
Join: `5b4739f906954cbe90a4b4adc73ad95b`

Keep each observation and relation at the map's own node in one memory layer that follows the same visibility rules as every layer.


#### Receiver: `code.server.mcp`

**Provider: `code.system.plugin`**  
Join: `894f333275494a01be94259971de55c1`

Serve exactly the tools of the modules on the folder's command surface, as they are declared now.

**Provider: `code.interface.command_line`**  
Join: `a6c759633b0e4cadbe25cbe7ae5e61cc`

Check each tool call's arguments exactly as the command line would, and fail with the command line's next step.

**Provider: `document.instructions.agent`**  
Join: `dfe87294592043789fb40e5c25a80629`

Give the host's agent Metaform's instructions when it connects.


#### Receiver: `code.gui.web`

**Provider: `code.store.graph`**  
Join: `b8d694476a804175b78735a85b5620fc`

Show every project's map exactly as agents would see it with the chosen layers, and change stored data only by peeling the top correction layer.

**Provider: `code.interface.command_line`**  
Join: `14f3f0e0062943c0a4cf93bea23dec28`

Apply the layer choice made in the browser to the project folder, so agents working there receive it, only when the orchestrator asks.


#### Receiver: `code.installer`

**Provider: `code.builder.package`**  
Join: `b789501572d541f28d0d5010e45a1923`

Register a wheel that holds the Metaform the user runs now.

**Provider: `code.server.mcp`**  
Join: `9d5130b15f5247f4b0749cacf7e47040`

Prove each registered tool can start Metaform's server before setup says it is done.


#### Receiver: `code.builder.package`

**Provider: `code.system.plugin`**  
Join: `241ec4524c494460a468387c24ffdab3`

Carry exactly the modules that are loaded, each with what it declares it needs.


#### Receiver: `document.instructions.agent`

**Provider: `code.system.plugin`**  
Join: `86cdff1139ed49bf994198956e6cff75`

Say what each enabled module is for, and add its current notice, without the chassis naming any module.


#### Receiver: `document.specification`

**Provider: `code.suite.test`**  
Join: `0774a5c4b78b436d8b0af88caf4f0b44`

Have each requirement's acceptance protected by a test that fails on a wrong build, on Linux, macOS and Windows, on every change.

### Internal subtypes and their containing purpose joins

The containment shown in this table refers to the join in which the provider supplies the receiver, not to a claim that every internal subtype is a lexical descendant of the provider address. A subtype does not become a duplicate global element merely because it has its own address and retained description.

| Internal address | Project name | Containing receiver <- provider |
|---|---|---|
| `document.procedure.intake` | Canonical Intake | `stakeholder.orchestrator.agent` <- `code.intake` |
| `code.writer.submission` | submission writer | `stakeholder.orchestrator.agent` <- `code.intake` |
| `code.tool.knowledge` | knowledge tool | `stakeholder.orchestrator.agent` <- `code.api.map` |
| `code.viewer.graph` | viewer | `stakeholder.orchestrator.agent` <- `code.gui.web` |
| `code.editor.prompt` | prompt editor | `stakeholder.orchestrator.agent` <- `code.gui.web` |
| `code.server.web` | web GUI server | `stakeholder.orchestrator.agent` <- `code.gui.web` |
| `code.launcher.variant` | web variants side by side | `stakeholder.orchestrator.agent` <- `code.history.variant` |
| `code.export.origin` | origin unit export | `stakeholder.orchestrator.agent` <- `code.history.variant` |
| `code.probe.server` | server probe | `stakeholder.orchestrator.agent` <- `code.installer` |
| `code.verifier.skill` | skill load check | `stakeholder.orchestrator.agent` <- `code.installer` |
| `document.skill.agent` | Metaform skill | `stakeholder.orchestrator.agent` <- `document.instructions.agent` |
| `document.rules.collaboration` | CLAUDE.md | `stakeholder.orchestrator.agent` <- `document.specification` |
| `code.template.module` | template | `stakeholder.author.module` <- `code.system.plugin` |
| `code.module.example` | helloworld | `stakeholder.author.module` <- `code.system.plugin` |
| `code.registry.project` | project registry | `code.chassis` <- `code.store.graph` |
| `code.stack.correction` | correction stack | `code.chassis` <- `code.store.graph` |
| `code.resolver.layer` | layer selection | `code.chassis` <- `code.store.graph` |
| `code.tracker.challenge` | challenge states and plans | `code.chassis` <- `code.store.graph` |
| `code.exchange.data` | export and import | `code.chassis` <- `code.store.graph` |
| `code.store.prompt` | prompt store | `code.chassis` <- `code.store.graph` |
| `code.schema.settings` | settings | `code.chassis` <- `code.interface.command_line` |
| `code.screen.settings` | settings screen | `code.chassis` <- `code.interface.command_line` |
| `code.interface.query` | query | `code.chassis` <- `code.interface.command_line` |
| `code.parser.declaration` | declaration reader | `code.chassis` <- `code.system.plugin` |
| `code.bus.event` | event bus | `code.chassis` <- `code.system.plugin` |
| `code.integration.continuous` | CI | `document.specification` <- `code.suite.test` |

The export's five findings concern the `ef` interface, side-by-side variant launching, origin-unit export, installed-skill verification, and CI lint results. Since then the map interface writes `ef` on `add-join` and `add-subtype`, [C01](#c01). A subtype flagged missing remains part of the represented function; consult [localized correspondence](#correspondence) and [supporting capabilities](#supporting) before treating its name as an implemented command.

Source: [the September 26 project export](../examples/project-metaform.json).

---

[Technical reference](REFERENCE.md) | [Examples to collect](EXAMPLES_TO_COLLECT.md) | [Ideas](IDEAS.md)
