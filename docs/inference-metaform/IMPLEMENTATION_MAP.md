# Inference Metaform: implementation map

[Technical reference](REFERENCE.md) | [Examples to collect](EXAMPLES_TO_COLLECT.md) | [Ideas](IDEAS.md)

This document connects the [described mechanisms](REFERENCE.md) to the supplied source snapshot, project graph, operative resources, and tests. It separates implemented facilities from the producers that use them and keeps specific source/intent differences at their actual locations.

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
15. [Complete current graph index](#graph-index)

<a id="snapshot"></a>
## 1. Snapshot and evidence basis

### Source identity

The supplied bundle identifies branch `chassis` and commit:

```text
ce9062bdec9398ca1f23ac60684bd3cc7e37f23c
```

That attribution comes from `BUNDLE_INDEX.txt`; the source copy contains no `.git` directory. The bundle reports no uncommitted changes in its included source, an omitted modified README, and an included untracked `uv.lock`. Documentation here is tied to those supplied bytes, not to an independently fetched current branch.

The operative intake resource is:

```text
src/metaform/modules/intake/resources/Canonical_Intake.xml
```

It is byte-identical to `specifications/Canonical_Intake.xml`, with SHA-256:

```text
7e2140a9dd71c875689604772c07e5f0c1dd6366b55ba03a530211867eb909f8
```

The standalone project JSON is the supplied `exports/metaform-main.json` with one change: each join and subtype row records `verb` as null, because that intake was made before `verb` existed. The current graph names Metaform `main`, id `6a339171fe6f44c49a40f4a270d98913`, with intake layer `2f6b86ffc49c4575bfdbf0ad2ac712f7`, named `intake-20260926T192840Z-f04016`, created September 26, 2026 at 19:28:40 UTC. Its recorded result id is `metaform-intake-20260926-a823b992`.

### What was checked

The documentation work used static source inspection, the supplied source-review results, archive hash verification, export inspection, and a read-only SQLite integrity/count check. The database returned `ok` from `PRAGMA integrity_check`. The application, module workflows, test suite, linter, and package build were not executed for this documentation. No implementation source was modified.

| Supplied current data | Count |
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

Selections and the correction stack are empty in this particular export. These counts identify available stored material; they do not define the capabilities of the store.

### How to read the evidence

**Author-described functionality** establishes the semantic mechanism and its intended use. **Inspected source** establishes present behavior. **Supplied operational observations** belong to their recorded run. **Derived illustrations** explain a use of the mechanism without claiming a new execution.

The current project graph is evidence of a functional representation, not an exhaustive code architecture. Its entries can also describe intended functionality with an accompanying missing flag. A represented node is therefore not, by itself, proof that its producer is implemented; an absent node is not proof that a shared facility is absent.

Relative source links assume these documents are placed at `docs/inference-metaform/` in the supplied repository layout. Export and historical-example paths refer to the accompanying source bundle; externally collected report/database paths are identified as such. The source tree is not duplicated in the documentation archive.

<a id="overview"></a>
## 2. Mechanism correspondence at a glance

| Mechanism | Project correspondence | Existing support / implementation boundary |
|---|---|---|
| Functional construction | `code.intake`; internal `document.procedure.intake` and `code.writer.submission` | Served Canonical Intake, agent-submitted element array, atomic base-layer writing. |
| Type and project naming | Element addresses, descriptors, namespace prefixes | Computed full/short readings and separately retained project names. |
| Reified relationships | Joins and internal subtypes in `code.store.graph` | Independent identities and node-targeted items. |
| Exact semantic identity | Provider-side `Store.identity` read | Retrieves receiving joins; no semantic equivalence prover or supplied formal resolution mapping. |
| Knowledge selection | Internal `code.resolver.layer` | Starting set, prefix select/mask, hidden-source closure, separate corrections. |
| Scoped inherited knowledge | `Store.context`; properties | Separate applying and visible properties; local items do not inherit. |
| Shared memory | `code.memory.agent` | Nine memory operations over graph nodes; mutable, unversioned memory layer. |
| Prompt versions | Internal `code.store.prompt`; web prompt editor | Version and use records exist; current intake does not populate them. |
| Project-grounded lexicalization | Intended operation described in the reference | Name/address, context, layer, and prompt facilities exist; no shipped lexicalization producer is identified. |
| Blindspot challenge exchange | Internal `code.tracker.challenge`; map answer/approve | State and plan storage exist; producing the critique and coupling prose rationale to state remain separate. |
| Community extension | `code.system.plugin`; `code.chassis` | Module contract, discovery, settings, Context, lifecycle, events, commands/tools, instructions. |
| Artifact realization history | `code.history.variant` | Origin, variant, reconstruction, and extraction operations; separate planned launch/export features are not inferred as implemented. |
| Visual and tool encounters | `code.server.mcp`; `code.gui.web`; `code.interface.command_line` | Shared data operations through different interfaces. |

<a id="records"></a>
## 3. Records, names, relationships, and reads

### Data model

The public `Store` delegates into the data package. The core record definitions and SQLite schema distinguish elements, joins, subtypes, items, properties, refs, layers, provenance, selections, findings, challenges, plans, and current/correction views.

An element has an identity and a namespace address. Its descriptor is an item carrying the project `name`, `name_length`, role, and associated refs. Address identity and a descriptor's wording are therefore separate. A join identifies its receiver and provider and carries `purpose`, `function`, `ef`, `relation`, `observation`, and optional additional fields. An internal subtype belongs to a containing join and has its own identity and functional description, without a separate parent-level purpose.

| Source | Symbols and relevant behavior |
|---|---|
| [records.py](../../src/metaform/data/records.py) | Record types, `Node`, elements, joins, subtypes, items, properties, layer and context results. |
| [schema.py](../../src/metaform/data/schema.py) | Tables and indices for stored records and their relationships. |
| [writes.py:43-207](../../src/metaform/data/writes.py#L43-L207) | `add_element`, `add_join`, `add_subtype`; descriptor handling and dedicated `ef` fields. |
| [writes.py:251-308](../../src/metaform/data/writes.py#L251-L308) | `add_item` targets a node; `add_property` attaches to an element. |
| [names.py](../../src/metaform/data/names.py) | `reading`, `short_name`; reverse segments and expand underscores. |
| [roots.json](../../src/metaform/data/roots.json) | Current five root types as data. |

`short_name` uses the last `name_length` segments. For `code.system.plugin`, length 2 produces `plugin system`; the descriptor's project name is `module contract and loader`. A missing/false or overlong lookback returns the full reading in the helper. That fallback is implementation behavior, not a semantic judgment that a malformed name is a good type.

### Relationship addressability

`Store.node` groups items at an element, join, or subtype by their layer. `links_to` finds items linking to a node. `citing` locates records with a matching ref key/value. `where` can locate a global element or an internal subtype and its containing join. `children` traverses namespace types rather than pretending every type prefix is a separately instantiated global element.

`Store.identity(element)` returns current joins for which that element is provider, including receiving purposes and EFs. It is useful for examining who receives a capability. Its name does not change its implementation into the exact semantic definition of `C(T)`.

Sources: [Store reads:263-341](../../src/metaform/data/store.py#L263-L341), [reads.py](../../src/metaform/data/reads.py), and [views.py](../../src/metaform/data/views.py).

### Known Function/Encounter interface difference

The store and intake support `ef`; the map knowledge interface does not fully pass it through. See [C01](#c01) for the exact interface paths. This is a localized correspondence issue, not a missing semantic distinction in the whole record model.

<a id="intake"></a>
## 4. Canonical Intake: resource to stored result

### Operative text

| Resource range | Content |
|---|---|
| [8-23](../../src/metaform/modules/intake/resources/Canonical_Intake.xml#L8-L23) | AUE, Entity, Element, VE, PE, OP, EF, DE, SE, NE, Parametric, and namespace concepts. |
| [24-47](../../src/metaform/modules/intake/resources/Canonical_Intake.xml#L24-L47) | Vested-entity rules and photo examples. |
| [51-94](../../src/metaform/modules/intake/resources/Canonical_Intake.xml#L51-L94) | Namespace meaning, reversible readings, valid prefixes, `name_length`, roots, and validity examples. |
| [96-114](../../src/metaform/modules/intake/resources/Canonical_Intake.xml#L96-L114) | Survey, receiving-purpose recursion, closure, annealing, convergence, and internal subtypes. |
| [115-144](../../src/metaform/modules/intake/resources/Canonical_Intake.xml#L115-L144) | Functional scope, artifact-specific joins, completion, exact address references, and response rules. |
| [145-175](../../src/metaform/modules/intake/resources/Canonical_Intake.xml#L145-L175) | Illustrative XML output shape, including nested subtype joins. |

The live prompt is not merged with the historical test/old/archive variants. It is the resource loaded by the module when the explicit override is empty.

### Serving

In [intake/__init__.py:33-87](../../src/metaform/modules/intake/__init__.py#L33-L87), `served` loads the resource or selected `intake_file`, substitutes the target's type/value and any `{project_id}`, and appends `footer`. The footer always contains the submission and stop/report instruction; project-report and process-feedback requests follow the call's report/debug settings.

The implementation retains exact operative wording through this path. Its optional override is an existing operation, not an encoding implementation. Copy and substitution tests are in [test_intake.py:62-89](../../src/metaform/modules/intake/tests/test_intake.py#L62-L89).

### Submission

`_elements` receives an array over MCP. On the CLI, it can read JSON from a file or standard input. `submit` creates the intake layer and uses `Writer` to store elements followed by their joins in one `Store.atomic` block. An unreadable top-level array returns a notice and no map; readable content is retained with notices where fields do not fit.

`Writer` retains unknown additions in extra content, records missing or unsupported fields with paths, and handles references to providers not yet represented. A subtype's independently supplied purpose is preserved in extra rather than silently installed as a second purpose field.

A repeat intake targets a new Metaform, and that new target is withdrawn if the atomic write fails. After successful storage it becomes active. Reports are saved after the map transaction, linked to the layer. Thus atomic map storage and report-file persistence are related operations, not one undifferentiated transaction covering every external file.

Sources: [submission entry:94-182](../../src/metaform/modules/intake/__init__.py#L94-L182), [writer](../../src/metaform/modules/intake/submission.py), [input schema](../../src/metaform/modules/intake/schema.py).

### Current example and source assertions

The supplied current export contains the one stored intake identified above. The [kitchen-timer fixture](../../tests/fixtures/intake_timer.json) is a smaller exact example of input shape: a cook receives a countdown function; the timer receives an audible alarm encounter; a tick-loop subtype is nested inside a join. It is a fixture, not an executed model performance result or an authoritative validation of every semantic placement.

The intake tests inspect complete writes, `ef` fields, missing content notices, duplicate-address handling, second-intake preservation, report linkage, non-software inputs, override selection, and the intentional absence of prompt-store records. The relevant cases are listed in [section 14](#tests).

<a id="selection"></a>
## 5. Selection, properties, and visibility

### Resolver behavior

[selection.py:91-156](../../src/metaform/data/selection.py#L91-L156) implements `Resolver`. Its incoming root is an explicit root selection when provided, otherwise nonempty toggled names, otherwise all finished, nonhidden, non-correction layers. An explicitly empty root and an absent root therefore have different meanings.

At each prefix the resolver removes mask rows and adds selectable select rows. When there is no local row for a layer, its incoming membership is preserved. This implements `(incoming & mask) | select` with sparse sets. A descendant select can restore a layer masked by an ancestor, without selecting the parent or a sibling.

[hidden_closure](../../src/metaform/data/selection.py#L56-L71) repeatedly adds layers whose recorded sources intersect the hidden set. That transitive closure is specific to `layer_sources`; it is not a blanket inference that any semantically associated layer is invalid. Building layers are excluded. Finished corrections participate through their separate application rules.

### Views

[reads.context:226-259](../../src/metaform/data/reads.py#L226-L259) returns `applying` properties on the prefix chain and `visible` properties on descendants. A property encountered during ancestor inspection retains the attachment scope at which it was resolved. Local item reads are separate.

The [C++/Bash source test](../../tests/test_store_layers.py#L289-L327) establishes the intended distinction in its assertions: both properties are visible at `code`, neither applies there, and a language property on one branch does not apply to another. A separate assertion shows an item staying local while a property follows its element's applicable scope.

Direct named `layer_items` can inspect hidden or masked content unless `in_context=True` is requested. Raw reads explicitly widen the view. Therefore comments describing universal exclusion must be read together with each public operation's view controls. Selection governs context, not deletion or a security boundary. See [Store.layer_items](../../src/metaform/data/store.py#L294-L303).

### Source-specific implication

This is implemented support for scope-sensitive knowledge and the author's Encounter propagation account. It does not, by itself, construct a language Encounter or infer all of its consequences. The producing inference operation remains distinct from the storage and view mechanics.

<a id="memory"></a>
## 6. Memory

`code.memory.agent`, named `memory module`, maps to [modules/memory/__init__.py](../../src/metaform/modules/memory/__init__.py). `_memory` finds the layer by kind or creates a ready, mutable, hideable `memory` layer on first write. [Layer creation](../../src/metaform/data/layering.py#L98-L111) deliberately skips provenance for memory.

An observation is an item at a node; a relation is an item at its from-node with a link to its to-node. Joins use ids; elements and subtypes can use addresses or ids. `open_nodes` presents related memory, while `read_graph` requests the memory layer in context. The mutation helper `_at` deliberately reads the layer directly to change its items.

The nine operations are declared as module verbs and become MCP tools through the common module contract. `create_entities` can create an element in the memory layer. `delete_entities` removes memory items at requested nodes, not their underlying map identities.

[update_item and delete_item](../../src/metaform/data/writes.py#L338-L356) modify/remove memory in place. Memory has no own edit history in this snapshot. Claims that every memory is immutable, versioned, or provenance-linked would therefore misstate the implementation.

Inspected tests include [join-addressed memory](../../src/metaform/modules/memory/tests/test_memory.py#L59-L76), [deletion semantics](../../src/metaform/modules/memory/tests/test_memory.py#L78-L92), and [selection](../../src/metaform/modules/memory/tests/test_memory.py#L123-L135). No memory observations from a current live project run are included in the supplied export.

<a id="corrections"></a>
## 7. Corrections and re-examination

The current map retains `code.stack.correction` as an internal contribution of the graph store to the chassis. Implementation is in [corrections.py](../../src/metaform/data/corrections.py), [layering.py:245-318](../../src/metaform/data/layering.py#L245-L318), and the `Store.correct`, `finish`, `peel`, `history`, and `peel_preview` APIs.

A correction is assembled while building and applied when finished. Current records are recomputed against the applied stack. The top correction can be peeled, returning it to building and recomputing affected current views. Correction layers are not normal selectable/hideable knowledge layers.

Relocation preserves an element id but writes removals for its relevant Metaform joins and their subtypes. Attached items remain associated with that element identity. Removing an element can orphan knowledge; restoring it restores the contextual relationship. Knowledge joins and base Metaform joins have their source-specific handling, so relocation is not simply a string substitution applied to every connected record.

The source marks layers built from the original adding layer for re-examination when the relevant correction applies. It does not implement an unspecified universal transitive semantic invalidation algorithm. The hidden-layer source closure and correction re-examination are different mechanisms.

A further lifecycle detail matters for ordinary knowledge: `writes.unchangeable` protects intake and finished corrections and redirects memory to its own mutation APIs. Ordinary knowledge records can be edited in place, including after finish; this guard does not treat their declared `mutable` value as a universal immutability switch. See [writes.py:361-369](../../src/metaform/data/writes.py#L361-L369), [edit:443-481](../../src/metaform/data/writes.py#L443-L481), and [the finished-layer test](../../tests/test_store_layers.py#L245-L260).

Inspected correction tests cover precedence, history, peeling, orphan/restoration, relocation, re-examination, and retention of `ef`: [test_store_corrections.py](../../tests/test_store_corrections.py).

<a id="prompts"></a>
## 8. Prompt versions and lexicalization

### Existing prompt facilities

The internal project address is `code.store.prompt`; its source is [data/prompts.py](../../src/metaform/data/prompts.py).

`add_prompt` creates a prompt and version 1. `add_prompt_version` creates a parent-linked next version, or returns the parent with a notice for identical text. `shipped` supports a shipped prompt's evolution while retaining a saved edit. `record_use` links a version to a project, Metaform, and layer. Reads expose versions and the layers associated with a version.

The web prompt editor uses these facilities. The existence of the editor and APIs is independent of whether the supplied home currently has prompt records.

### Current intake usage

The intake's provenance explicitly stores `prompt=None`; it does not call the version store to preserve the served text. The bundle identifies no populated prompt store, and the intake tests explicitly assert that serving the resource creates no stored prompt version. See [intake provenance](../../src/metaform/modules/intake/__init__.py#L153-L160) and [tests:390-418](../../src/metaform/modules/intake/tests/test_intake.py#L390-L418).

### Intended lexicalization producer

The author-described operation is fully defined in [REFERENCE.md](REFERENCE.md#lexicalization): infer referents against the project, substitute recorded project names without paraphrase, attach canonical-term-to-namespace mappings and knowledge directions, identify any selected imperative contribution, and stop before execution.

The source supplies the useful ingredients: names and addresses, relationship reads, node memory, layer selection, prompt versions, Context, module tools, and instructions. No shipped module in this snapshot performs that task-specific preprocessing as a lexicalization producer. Prompt versioning is not lexicalization, and composing module-purpose instructions is not the same operation.

No current before/after lexicalized prompt pairs were supplied. The reference's pair uses a real project name but is marked as a derived illustration. Original pairs and their selected knowledge are a collection target, not a precondition for describing the intended operation.

<a id="challenges"></a>
## 9. Blindspot challenges and plans

The map represents `code.tracker.challenge` inside the graph store's receiving relationship with the chassis. The state implementation is [data/challenges.py](../../src/metaform/data/challenges.py), exposed through [map answer/approve](../../src/metaform/modules/map/__init__.py#L479-L485) and Store operations.

`answer` stores a state in `A`, `B`, or `C`, optional C target, and timestamp, associated with a critic item. A C without a link is retained with a notice. Unsupported answer words are handled as specified by the operation; `plan` is not an agent answer that directly substitutes for approval.

`approve` operates on B and updates the disposition to plan. It can create a plan row when the challenge item targets an element added by the critic's layer. The exposed approval verb is CLI-only. Separately, `add_plan` creates a plan directly without a challenge approval. The source's header comment saying a plan comes only from approval is narrower than the actual public operations; the direct operation is implemented and tested.

The answer API has no prose-rationale parameter. Its state table therefore is not the complete conceptual blindspot answer. A substantive response includes reasons, unexplored relevance, or where and how functionality is already supplied. Existing items/layers can store those explanations, but the snapshot does not demonstrate a producer automatically writing a prose answer alongside its disposition.

The shipped modules include no independent blindspot-producing workflow. That producer boundary does not remove the implemented challenge tracker or shared inference/module facilities. The current export contains no challenge states or plans.

Source assertions: [state/link behavior](../../tests/test_store_challenges.py#L26-L41), [approval and critic-layer preservation](../../tests/test_store_challenges.py#L44-L59), and [direct planning](../../tests/test_store_challenges.py#L62-L72).

<a id="extensions"></a>
## 10. Community extension and execution facilities

### One contract, several receiving purposes

`code.system.plugin`, named `module contract and loader`, is supplied to module authors, the chassis, CLI, MCP, builder, and agent instructions. Its two internal module-author examples are `code.template.module` and `code.module.example`.

| Capability | Concrete implementation |
|---|---|
| Module declaration | [Module, Verb, Noun, Subscription, Status](../../src/metaform/module.py#L43-L130). |
| Per-call context | [Context](../../src/metaform/module.py#L133-L176), [context.build](../../src/metaform/context.py). |
| Settings declaration and resolution | [settings.py](../../src/metaform/settings.py), module-owned registrations in loader. |
| Discovery | [loader._candidates and discover](../../src/metaform/loader.py#L56-L192): system, user-home, entry points. |
| Metadata before import | [module_metadata.py](../../src/metaform/module_metadata.py): literal metadata inspection. |
| Task ownership | [loader.spawn and task completion](../../src/metaform/loader.py#L204-L230), unload/reload/shutdown paths. |
| Shared store | `Context.require_store` and [Store](../../src/metaform/data/store.py). |
| Command surface | [cli.py](../../src/metaform/cli.py), [grammar.py](../../src/metaform/grammar.py). |
| MCP tool surface | [MCP server](../../src/metaform/modules/mcp/server.py). |
| Agent instructions | [instructions.compose](../../src/metaform/instructions.py#L50-L66). |
| Empty template | [template](../../src/metaform/modules/template/__init__.py). |
| Working demonstration | [helloworld](../../src/metaform/modules/helloworld/__init__.py). |

Metadata can be read from recognized literal declarations, including the reader's supported `manifest.py` fallback; the shipped template uses `__init__.py`. This is a description of source compatibility, not a new requirement to add manifests.

The loader records disabled, incompatible, missing-dependency, and failed candidates separately. Its module id precedence is determined by discovery order. Import registers settings under module ownership; unload withdraws owned registrations and tasks while leaving stored data. The source includes both synchronous and asynchronous lifecycle paths; owned coroutines require an available running loop when spawned.

### Shipped modules

| Module | Function in this snapshot | Shipped default |
|---|---|---|
| `intake` | Serve intake, accept the final array, report intake state. | Enabled |
| `map` | Graph reads, knowledge and correction operations, selection, challenges/plans. | Enabled |
| `memory` | Shared observations and relations at map nodes. | Enabled |
| `mcp` | Serve the generated tool surface over stdio. | Enabled |
| `web` | Detached graph and record inspection interface. | Enabled |
| `helloworld` | Exercise the public module contract and shared capabilities. | Disabled |
| `template` | Empty module starting point. | Disabled |

These are declaration defaults, subject to persisted enablement and environment compatibility. The availability of a chassis facility is not proportional to how many current modules call it.

### CLI/MCP and instructions

The MCP server derives schemas from verbs, nouns, relevant settings, and operation-specific controls. It creates a Context, awaits coroutine verbs, and offloads plain verbs to a worker thread. Its tool list is rebuilt on requests. The server's instruction text is composed when constructing the server; it is not rebuilt merely because a tool-list request occurs.

Consequently, a module or surface change can affect subsequent tool lists while an already connected host retains the instruction text supplied at initialization until reconnection. See [server.py:299-357](../../src/metaform/modules/mcp/server.py#L299-L357) and [instructions.py](../../src/metaform/instructions.py).

<a id="events"></a>
## 11. Event delivery and the earlier illustration

The current project map places `code.bus.event` inside the join where the plugin system serves the chassis. Current source is [events.py](../../src/metaform/events.py), exposed through `Context.publish` and `Context.publish_async`; task creation is separately exposed through `Context.spawn`.

`publish` iterates matching loaded subscriptions, builds the receiver's Context, deep-copies the payload, and calls the handler before moving on. `publish_async` likewise processes each matching subscription, awaiting coroutine handlers or awaiting `asyncio.to_thread` for a plain handler. Both report per-subscriber outcomes. In the async path, cancellation of the publisher task is re-raised rather than merely converted into one subscriber result.

This establishes individual attribution and isolation of reported subscriber failures. It also establishes that the publication call waits for its sequence of deliveries. Offloading synchronous work preserves event-loop availability; it does not mean the publisher returns before delivery, or that an arbitrary coroutine cannot block internally.

The author's earlier `code.bus.data.event -> code.runtime.execution` example described an illustrative purpose of attributable work that does not block the publisher or another module. It is not a literal inventory of the current source. The current map's different names, or absence of a separately named runtime node, do not prove any scheduling architecture. The distinction is established by inspecting the actual delivery and task code.

Relevant source assertions are in [test_base.py](../../tests/test_base.py), including individual outcomes and a running loop during awaited delivery, and [test_lifecycle.py](../../tests/test_lifecycle.py), including owned-task cancellation before stop. These are inspected assertions, not newly executed results.

<a id="supporting"></a>
## 12. Other implemented project capabilities

### Project registration and storage context

[home.py](../../src/metaform/home.py), [context.py](../../src/metaform/context.py), and [data/session.py](../../src/metaform/data/session.py) provide project registration, Metaform selection, and store access through the Metaform home. The current source uses `~/.metaform` or `METAFORM_HOME` for its state; a project's artifact path identifies what it examines rather than a requirement to place runtime state inside that project.

A per-call project or layer choice and a stored folder setting are separate inputs. Context construction resolves those inputs for the operation. This is part of supplying the same functional map through different host environments.

### Read and write encounters

`code.api.map` connects Store operations to verbs and tools. Its reads cover entry roots, location, elements, receiving/provider joins, identity, subtypes, children, node content, property context, links, refs, history, stack, search, layers, and findings. Knowledge operations create and populate layers, write records and plans, and manage corrections. Selection and challenge operations are additional explicit verbs.

`code.gui.web` supplies graph and record inspection over these stored operations. [server.py](../../src/metaform/modules/web/server.py) exposes named reads and three writes: apply layers to the project folder, save a prompt version, and peel/discard the top correction. [app.js](../../src/metaform/modules/web/page/app.js) and the page resources render the functional graph, purpose relationships, inspector, and prompt editing. They do not imply that every possible graph edit is a browser operation.

The graph view's purpose vertices make the receiving relationship visible rather than drawing only an unlabeled dependency. The stored graph's own internal subtype decomposition should still be distinguished from a code-module architecture diagram.

### Origins and variants

[history.py](../../src/metaform/data/history.py) implements repository/plain-folder boundaries, origin creation, collecting variants against a selected origin, reconstructing their files, and extraction. Variants are stored relative to their origin rather than forming an implicit chain of unrelated worker deltas. Reconstruction checks recorded file hashes.

The repository boundary includes tracked files and untracked, nonignored files. The original intake report warns that the examined working tree contained substantial untracked historical material. That warning is a recorded observation of that run, not a newly measured inventory of the user's present checkout.

The supplied graph separately names intended side-by-side web-variant launching and origin-unit wheel export/import. Those features carry missing findings; ordinary variant reconstruction must not be described as proof they are complete. See [C10](#c10).

### Exchange, reports, build, and installation

| Project function | Source and current role |
|---|---|
| Graph export/import | [data/exchange.py](../../src/metaform/data/exchange.py): exchange of graph records and layers, with identity, dependency, and conflict handling. This is distinct from origin-unit wheel exchange. |
| Feedback and reports | [reports.py](../../src/metaform/reports.py), [Store report methods](../../src/metaform/data/store.py#L404-L419): retain project reports, process feedback, and shapes and associate available records with layers/runs. |
| Wheel construction | [build.py](../../src/metaform/build.py): build from loaded modules and declared dependencies, omit module tests, support pure-Python vendoring and directly runnable wheel packaging. |
| Host installation | [install.py](../../src/metaform/install.py): supported host registration, skill placement, recorded changes and backups, and removal of those changes. |
| Registered-server probe | [probe.py](../../src/metaform/probe.py): start the command being registered and check initialization/tool listing, then stop it. This is not the separate per-host skill-loading proof. |
| Test/CI functionality | [checks.yml](../../.github/workflows/checks.yml), [conftest.py](../../conftest.py), and tests: source definitions of cross-platform checks, fixtures, and execution assertions. |

<a id="correspondence"></a>
## 13. Localized correspondence issues

These entries preserve both the described semantics and the supplied source. They do not silently revise either one, and no code fixes were made as part of the documentation.

<a id="c01"></a>
### C01. Dedicated `ef` support is omitted by the map knowledge interface

**Source-inspected.** Intake and Store support `ef` on joins and subtypes. The map module's `FIELDS`, per-operation `READS`, declared knowledge nouns, and add dispatch omit it. `_unread` can retain an unrecognized add field in extra with a notice; that is not equivalent to filling the dedicated column. Edit/correct paths also do not expose the complete dedicated-field route through this interface.

Sources: [map fields](../../src/metaform/modules/map/__init__.py#L26-L28), [operation reads and dispatch](../../src/metaform/modules/map/__init__.py#L234-L321), [intake writer](../../src/metaform/modules/intake/submission.py#L131-L182), [Store add methods](../../src/metaform/data/store.py#L168-L191).

**Correspondence:** preserve Function/Encounter in the design and record model. The source-local repair area is the map interface, not removal or reinterpretation of the distinction.

<a id="c02"></a>
### C02. One live language-intake exclusion and the broader Encounter account coexist

**Literal operative text plus author-described mechanism.** The live [line 91](../../src/metaform/modules/intake/resources/Canonical_Intake.xml#L91) says:

```xml
<example namespace_address="code.cpp" valid="false" reason="this is language" />
```

The author's broader account attaches language Encounters such as `code.c` and allows `code.html` as a language Encounter, while rejecting encoding alone as a functional subtype. The property tests separately demonstrate scoped language-property application and visibility.

**Correspondence:** the supplied implementation does not specify a complete producer workflow connecting the functional intake-stage exclusion to subsequent language-Encounter attachment and inference. Neither changing the live example nor deleting language Encounters from the reference would establish that missing correspondence. The reference describes the mechanism; this entry preserves the exact source boundary.

<a id="c03"></a>
### C03. A broad stored provider and the single-EF semantic Type are different levels of description

**Author definition plus literal source representation.** The exact identity definition uses one `e` per semantic Type at its represented resolution. The intake's EF definition at [line 18](../../src/metaform/modules/intake/resources/Canonical_Intake.xml#L18) says that a PE type on the whole can serve different VEs through different Encounter Functions, each recorded in its receiving join. Current stored providers accordingly have several receiver-specific descriptions.

**Correspondence:** no complete formal mapping from those broad provider records to the resolution-specific Type is supplied. `Store.identity` retrieves those relationships; it does not resolve the semantic correspondence by proving equivalence. The exact definition is retained without inventing a canonicalization rule, subtype split, or runtime approval mechanism.

<a id="c04"></a>
### C04. Challenge state does not itself store the substantive answer

**Source-inspected.** `answer` takes item, state, and optional link. The resulting state record has no explanation field. The conceptual challenge requires the project's reasoning.

**Correspondence:** item and layer facilities can hold that explanation, but automatic coupling to the state operation is not demonstrated. The existing B approval and direct-plan routes remain as implemented; neither is made into a new general gate on inference. See [section 9](#challenges).

<a id="c05"></a>
### C05. Lexicalization and criticism producers are not replaced by their supporting facilities

**Source inventory and author account.** The snapshot contains the seven modules listed above. It contains names, layers, prompts, context, memory, and challenge states but no identified shipped producer for project-grounded prompt lexicalization or the full critic/challenge exchange.

**Correspondence:** describe those intended operations from the author's explanations and their support from source. Do not label the prompt store a lexicalizer, the challenge tracker a critic, or the absence of either producer an absence of community extension.

<a id="c06"></a>
### C06. Retention, editability, and participation have distinct implementations

**Source-inspected.** Memory is mutable and unversioned; ordinary knowledge records can be edited in place; intake and finished corrections are protected by different rules; prompt versions retain text immutably. Hiding and masking exclude context without deleting content, and explicit named/raw reads can inspect retained content.

**Correspondence:** descriptions such as every layer is immutable, every memory has provenance, or every hidden item is inaccessible through all reads would be incorrect. The exact layer lifecycle is the basis for explaining reuse and history. See [sections 5-8](#selection).

<a id="c07"></a>
### C07. Intake preservation is implemented; encoding is an author intention without a selected mechanism

**Source-inspected and author-described.** Exact resource text, controlled substitutions, copy tests, and an explicit override exist. No encoding, encryption, obfuscation, or decoding service is specified in this snapshot.

**Correspondence:** preserving operative behavior on release does not justify inventing a secrecy scheme or asserting that the intake will never be published. The full operative material is appropriate to this internal reference.

<a id="c08"></a>
### C08. XML elicitation and array submission are separate stages

**Source-inspected.** The resource requests final XML; the module's submission tool accepts an array and the CLI reads its JSON representation. It does not parse that XML.

**Correspondence:** the agent performing the intake supplies the tool's data shape. The resource is a model-directed procedure; neither XML parsing nor structural checks amount to deterministic semantic execution of the intake. See [section 4](#intake).

<a id="c09"></a>
### C09. The resource's role prose and schema differ on `AUE`

**Literal resource and current export.** The response prose says an inside element has one role among `DE`, `SE`, and `NE`, while an outside VE has `VE`. The illustrative outer element schema at [line 149](../../src/metaform/modules/intake/resources/Canonical_Intake.xml#L149) also includes `AUE`. The current map uses `AUE` for `code.graph.knowledge` and `DE` for `code.chassis`.

**Correspondence:** this is recorded as a local role-schema distinction requiring alignment, rather than silently expanding the role prose or rewriting the current export. It does not change the Entity/Element or receiver/provider semantics.

<a id="c10"></a>
### C10. The current map includes three intended features with missing findings

**Supplied graph observations, with current source boundaries.**

| Represented contribution | Recorded intended function | Status relevant to this documentation |
|---|---|---|
| `code.launcher.variant` | Serve web variants on separate ports for side-by-side inspection. | Marked missing in the supplied graph/report; existing history extraction is not this launcher. |
| `code.export.origin` | Export/import a complete origin unit as a reconstructable wheel. | Marked missing; current graph-data exchange and ordinary package building are different capabilities. |
| `code.verifier.skill` | Verify that each host actually loads the skill from the installed folder. | Marked missing; successful MCP server probing does not perform that host-specific skill check. |

The source inventory does not identify completed implementations of these producers. Their functional descriptions can remain in the graph as intended contributions. Their implementation must not be inferred from a broad neighboring capability.

<a id="c11"></a>
### C11. Reported test and lint results are historical run observations

The current intake report records `482 passed` for pytest, strict pyright with zero errors, and 117 Ruff findings. The corresponding graph flags CI lint as broken. These are supplied results from that intake run, not tests or lint executed for this reference. They are kept as available operational evidence without certifying the current live checkout.

### Event scheduling and instruction refresh

The earlier bus/runtime illustration versus current sequential awaited delivery is explained in [section 11](#events). Request-time tool-list regeneration versus server-construction instruction composition is explained in [section 10](#extensions). Both are established from code rather than inferred from graph naming.

<a id="tests"></a>
## 14. Tests and available operational evidence

### Inspected source assertions

| Mechanism | Test source and representative cases |
|---|---|
| Intake integrity | [test_intake.py:62-89](../../src/metaform/modules/intake/tests/test_intake.py#L62-L89): byte copies, target-only substitution, footer settings. |
| Intake field retention | [test_intake.py:108-253](../../src/metaform/modules/intake/tests/test_intake.py#L108-L253): whole write, `ef`, `verb`, missing fields, extra content, unreadable top-level input. |
| Repeated intake and non-code artifacts | [test_intake.py:255-378](../../src/metaform/modules/intake/tests/test_intake.py#L255-L378): new active Metaform, duplicate addresses, report/flags, non-software fixture. |
| No implicit prompt version | [test_intake.py:390-418](../../src/metaform/modules/intake/tests/test_intake.py#L390-L418). |
| Local selection and inheritance | [test_store_layers.py:141-173](../../tests/test_store_layers.py#L141-L173), [289-327](../../tests/test_store_layers.py#L289-L327), [349-400](../../tests/test_store_layers.py#L349-L400). The select test is named `test_a_select_toward_the_leaves_from_a_mask_turns_the_layer_on_again_there_and_nowhere_toward_the_trunk`, naming the direction by the tree's parts. |
| Knowledge and memory lifecycle | [test_store_layers.py:124-138](../../tests/test_store_layers.py#L124-L138), [230-277](../../tests/test_store_layers.py#L230-L277). |
| Relationship-addressed memory | [memory tests](../../src/metaform/modules/memory/tests/test_memory.py): join nodes, relations at both ends, deletion, selection, and newly noted elements. |
| Challenges and direct plans | [test_store_challenges.py](../../tests/test_store_challenges.py). |
| Corrections | [test_store_corrections.py](../../tests/test_store_corrections.py): precedence, peel, orphans, relocation, re-examination, and `ef`. |
| Prompt version/use | [test_prompts.py](../../tests/test_prompts.py): version retention, use linkage, shipped text, indexed reads. |
| Module lifecycle | [test_lifecycle.py](../../tests/test_lifecycle.py): spawned task completion before stop, unload/reload, settings restoration, dependency failure. |
| Event outcomes and async loop | [test_base.py](../../tests/test_base.py). |
| Module contract examples | [helloworld tests](../../src/metaform/modules/helloworld/tests/test_helloworld.py), [template tests](../../src/metaform/modules/template/tests/test_template.py). |
| MCP and web interfaces | [MCP tests](../../src/metaform/modules/mcp/tests/test_mcp.py), [web tests](../../src/metaform/modules/web/tests/test_web.py). |
| Variant history and exchange | [test_history.py](../../tests/test_history.py), [test_store_exchange.py](../../tests/test_store_exchange.py). |

These tests show expected operation and available coverage in source. A passing result is reported only where the original operational record reports it.

### Available run material

The original current run's report and feedback are in the supplied bundle under:

```text
external/metaform-home/projects/metaform/reports/
  2f6b86ffc49c4575bfdbf0ad2ac712f7-report.md
  2f6b86ffc49c4575bfdbf0ad2ac712f7-feedback.md
```

The earlier run has report/feedback files with id `70618d7651c24ba9b04219544af156d8`, but no retained export of its withdrawn Metaform. Historical intake outputs and the address-only/knowledge-layer examples are catalogued in [EXAMPLES_TO_COLLECT.md](EXAMPLES_TO_COLLECT.md#available). Their source roles are not merged with the current run.

<a id="graph-index"></a>
## 15. Complete current graph index

The following index is derived from the supplied `exports/metaform-main.json`, not from an invented decomposition of the code. It includes all 19 global elements, all 33 purpose joins, and all 26 internal subtypes in that export. It is an index to the represented functionality; implementation status remains governed by the sections above.

`document.specification` and the internal `document.rules.collaboration` are included because the supplied map represents them. The excluded narrative documents themselves were not used as a source for this reference.

### Global elements

<!-- Generated from the supplied project export. -->
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

The five supplied findings concern the `ef` interface, side-by-side variant launching, origin-unit export, installed-skill verification, and CI lint results. A missing-flag subtype remains part of the represented function; consult [localized correspondence](#correspondence) and [supporting capabilities](#supporting) before treating its name as an implemented command.

Source: [current project export](../examples/project-metaform.json).

---

[Technical reference](REFERENCE.md) | [Examples to collect](EXAMPLES_TO_COLLECT.md) | [Ideas](IDEAS.md)
