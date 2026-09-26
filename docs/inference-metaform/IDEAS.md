# Inference Metaform: additional ideas

[Technical reference](REFERENCE.md) | [Implementation map](IMPLEMENTATION_MAP.md) | [Examples to collect](EXAMPLES_TO_COLLECT.md)

These are proposals for making the Inference Metaform more useful and legible in repository work. They extend from the described mechanisms; they are not established architecture, requirements, or claims that the proposed functionality already exists.

The most useful additions would expose the system's central operation: **understanding is prepared, used, enriched, and used again**. A tool or document should help someone follow that operation rather than hide it behind another generic agent dashboard.

## Contents

1. [Make preparation and participation visible](#preparation)
2. [Make reuse, criticism, and change visible](#reuse-change)
3. [Show the receiving purpose of an operation](#receiving-views)
4. [Additional repository-facing documents](#documents)
5. [A practical order of work](#order)

<a id="preparation"></a>
## 1. Make preparation and participation visible

### Proposal 1. A readable task-preparation view

**Proposed functionality.** Show the original request beside the prepared request, with the exact project-name substitutions highlighted. Associate each substitution with its canonical term, namespace address, and the receiving-purpose context used to resolve it. Present knowledge directions and selected imperative additions as separately identifiable contributions.

**Benefit.** This makes lexicalization inspectable as project grounding, not a rewrite service. The user can immediately see whether the operation was preserved and which project understanding was supplied before execution. An agent can recover the same grounding without inferring it again from a polished narrative.

**Connection to existing mechanisms.** The [lexicalization mechanism](REFERENCE.md#lexicalization) defines the operation; the existing [name, node, and context reads](IMPLEMENTATION_MAP.md#records) supply its material. [Prompt versions and use records](IMPLEMENTATION_MAP.md#prompts) can retain a prepared prompt when a producer explicitly uses them. The lexicalization producer and this view would be additional work, not a relabeling of the existing prompt editor.

**Concrete illustration.** A user asks to examine how extensions become available to tools. The view preserves that request, shows the resolved project name `module contract and loader`, and maps it to `code.system.plugin`. It displays the relevant MCP receiving purpose and points to a selected observation about tool exposure. An added instruction to exercise a particular surface appears under its contributing layer, not disguised as words the user supplied.

The useful first form could be a plain-text report emitted by the eventual producer. A graphical comparison could follow without changing the operation or requiring a new prompt schema. Where a referent remains ambiguous, the view could preserve that ambiguity and its explicit resolution rather than concealing it in a rewritten sentence.

### Proposal 2. An explanation of why knowledge participates here

**Proposed functionality.** Add a readable explanation alongside a context result: the incoming selection, local masks and additions along the address path, the properties that apply from ancestors, properties visible on descendants, local items, and any hidden source relationship excluding a layer. Show corrections as their own contribution rather than pretending they followed normal layer masks.

**Benefit.** Users could understand why an agent received a particular instruction or failed to receive an expected observation. This is especially valuable when knowledge is correct but attached or selected at the wrong place. It would also make multidimensional prompting practical to inspect without requiring readers to reconstruct the resolver from database rows.

**Connection to existing mechanisms.** The [resolver and context implementation](IMPLEMENTATION_MAP.md#selection) already perform the underlying operations. The proposed addition is an explanation of those operations, not a different selection rule. [Local memory](IMPLEMENTATION_MAP.md#memory) must remain distinguishable from inherited properties.

**Concrete illustration.** A parent branch masks an old language layer; a particular descendant selects it again for an examination of a still-unported component. The explanation shows that path and the resulting knowledge. At a sibling, it shows that no such selection occurred. A parent can still discover a descendant property without the view calling it universally applicable to every child.

A useful implementation would derive the explanation from the same resolution decisions used to construct the context result. A separate explanatory algorithm could drift into giving a convincing but inaccurate account. The explanatory output can be optional; it need not expand every agent prompt or become a prerequisite to reading context.

### Proposal 3. A purpose-aware memory view

**Proposed functionality.** Display a memory item with the node that gives it meaning. At a join, show receiver, operative purpose, provider, Function/Encounter, and nearby source refs before presenting the observation. Offer navigation to the same provider's other receiving relationships without merging their knowledge.

**Benefit.** This would make the difference between remembering a fact and remembering its functional location visible. It would help an agent find a past conclusion at the relationship where it matters and help a user detect a note that was attached too broadly.

**Connection to existing mechanisms.** [Node-addressed items and relationship reads](IMPLEMENTATION_MAP.md#records) already support elements, joins, and subtypes. The proposal is a presentation and navigation capability over that data. It does not imply that mutable memory already has a historical ledger.

**Concrete illustration.** A note about how a declared verb appears as an MCP tool is shown at the MCP-to-module-contract relationship. A note about packaging the same module is shown at the builder's relationship. The module's name connects them for navigation, while their receiving purposes preserve why the observations differ.

The same view could distinguish an informational observation from an imperative contribution using the actual retained content. It should not silently promote every remembered sentence into a command. Historical comparison would require separately retained snapshots or explicit history work because the current memory layer changes in place.

<a id="reuse-change"></a>
## 2. Make reuse, criticism, and change visible

### Proposal 4. Trace one prepared understanding through several operations

**Proposed functionality.** Produce a small reuse report linking a prepared relationship or knowledge item to the later tasks that explicitly used it. Show what each operation received, what it produced, and what new understanding it retained. Keep the original preparation separate from later additions.

**Benefit.** This would explain advance inference amortization more convincingly than a feature list. It would also help repository workers locate useful earlier reasoning by the functional relationship it addressed rather than by remembering which conversation contained it.

**Connection to existing mechanisms.** The graph supplies stable node identities, [layers and provenance](REFERENCE.md#provenance) identify contributions, and prompt-use records can associate a stored prompt with a project, Metaform, and layer. These are ingredients, not an already complete per-item consumption log. An initial report can be assembled from actual exports, tool results, and task records using the [collection guidance](EXAMPLES_TO_COLLECT.md#reuse).

**Concrete illustration.** The module author's receiving purpose is established during intake. One task uses it to write extension instructions, another to implement a module, another to examine CLI/MCP consistency, and another to refactor loading. The report shows that shared purpose and the additional observations acquired during each task.

An explicit context read is evidence that material was supplied, not by itself proof of how much internal reasoning the model saved. The report can distinguish supplied context, an agent's recorded explanation of its use, and a later artifact showing a corresponding decision. That distinction makes the account more informative than counting reads as successful reuse automatically.

### Proposal 5. Compare changes through relationships, not just files

**Proposed functionality.** Add a comparison view organized around receiving purposes and their providers. Put graph changes, selected knowledge changes, and implementation changes alongside one another. Mark moves of realization separately from changes in purpose or Encounter, using the user's directed intent as the reference for interpreting the change.

**Benefit.** A reader could understand a refactor whose physical diff is large but whose functional identity remains, or a small code change whose effect alters an important receiving relationship. This would make recomposition visible at the level the Inference Metaform describes.

**Connection to existing mechanisms.** The [exact identity account](REFERENCE.md#identity) supplies the semantic distinction; [corrections](IMPLEMENTATION_MAP.md#corrections) and [artifact origin/variant history](IMPLEMENTATION_MAP.md#supporting) retain different change records. A comparison would need to connect those records explicitly. The existing `Store.identity` operation retrieves provider-side joins; it does not decide semantic equality for the proposed view.

**Concrete illustration.** Loader implementation is moved between files. The comparison still shows the module author receiving the ability to add a capability once and the MCP server receiving declared tool operations. A second change alters which operations modules can expose; its consequences are shown at those receiving relationships rather than hidden among file moves.

The comparison could show an explicit agent explanation of whether a relationship was preserved or intentionally transformed, with corresponding source locations. It should not claim that a string diff computes exact `C(T)` or that unchanged addresses establish identity. For a port, the display should retain the represented resolution: broad function can persist while a language-specific Encounter changes.

### Proposal 6. Make criticism's contribution to understanding persistent and readable

**Proposed functionality.** Present a critic's finding, the project's substantive response, the A/B/C state, supporting artifact location, and any subsequent plan or retained knowledge as one navigable exchange. Later criticism could consult that exchange through the affected functional node.

**Benefit.** A finding would stop being an isolated issue title. The project could preserve why something offered no benefit, why it remained unexplored, or where it was already handled. A later agent could reconsider the earlier reasoning in a changed context without either forgetting it or treating the old answer as unquestionable.

**Connection to existing mechanisms.** [Challenge state and plan storage](IMPLEMENTATION_MAP.md#challenges) exist; node-targeted items and layers can hold explanations. The current answer operation does not automatically write prose rationale. This proposal would connect those contributions deliberately and visibly rather than pretending the state row already contains them.

**Concrete illustration.** A critic questions whether unloading a module leaves its owned work running. The project gives a C response with the lifecycle implementation and explains the cancellation/await behavior. The exchange links to that relationship and the relevant source. If a later change introduces another execution path, the new critic can examine whether the previous explanation still covers it.

A B response can lead to a plan, but the view should not equate the response with approval or implementation. An A response can retain a useful explanation even when no change is made. The entry can also identify whether the critic examined source or only the map, without enforcing a particular order of examination.

### Proposal 7. Transfer useful understanding between workpieces without importing the wrong context

**Proposed functionality.** Show a candidate knowledge contribution from one workpiece beside the type ancestry and receiving relationships of another. Help an agent identify which part is type-level, which part depends on a particular Encounter, and which part is specific to the original project's realization. Retain the originating contribution when a new project-specific conclusion is derived.

**Benefit.** The system could reuse more than exact project memory. It could transfer useful functional understanding while keeping the differences that determine whether it applies. This would turn the shared type structure into a practical route for learning across workpieces, rather than a reason to copy whole layers indiscriminately.

**Connection to existing mechanisms.** [Primordial type understanding](REFERENCE.md#type-understanding), [property scope](REFERENCE.md#layers), addressed relationships, and provenance provide the foundation. A transfer workflow or interface would be new producer functionality. Sharing a type address would orient the analysis, not establish that every project-specific observation transfers unchanged.

**Concrete illustration.** One project's event-handling layer explains attributable failure reporting for handlers. Another project also supplies events but uses a different delivery schedule. The agent can reuse the functional consideration about attribution while examining scheduling and lifecycle in the target project. A note about the first project's exact blocking behavior stays attributed to its realization.

A non-code counterpart is a collection-level presentation practice that transfers between sale photographs, while observations about one photographed item's condition remain local. The useful output is a reasoned, scoped contribution to the target workpiece, not a second global repository of unqualified advice.

<a id="receiving-views"></a>
## 3. Show the receiving purpose of an operation

### Proposal 8. Receiver-oriented views of the same provider

**Proposed functionality.** Offer focused views of a capability according to the entity receiving it. Each view would show the relevant purpose joins, internal subtypes, selected knowledge, refs, and available operations. The views would be projections of the same Inference Metaform rather than separately maintained architecture descriptions.

**Benefit.** A module author, a packaging task, and a source critic do not need unrelated versions of the truth; they need different relationships within the same functional understanding. A receiver-oriented view would let a user enter at the purpose of the present task while retaining navigation to broader consequences.

**Connection to existing mechanisms.** The current [project graph](IMPLEMENTATION_MAP.md#graph-index) already represents the module contract serving the module author, chassis, command line, MCP, builder, and agent instructions. Existing reads and the web viewer provide a basis for focused presentation; the particular receiver-oriented interface would be additional work.

**Concrete illustration.** Entering through `stakeholder.author.module` presents the template and helloworld contributions and the capability to declare a module once. Entering through `code.server.mcp` presents the same contract as the provider of tool declarations and callable operations. Entering through `code.builder.package` presents its role in producing the distributed package.

This could also improve a module-author demonstration. A single example module could be shown being discovered, configured, called from available surfaces, supplied with context, and stopped with its owned tasks. The view would make visible both what the module provides and what it receives from shared facilities. It would avoid mistaking the number of current users of an event facility for the existence of the facility itself.

A receiver view is a navigation choice, not a reason to suppress broader affected purposes. The relevant joins should remain connected so a local change can be examined through the other entities it serves.

<a id="documents"></a>
## 4. Additional repository-facing documents

The technical-reference set supplies the full account, source correspondence, collection plan, and ideation. The README, first-session guide, module-author guide, reader guide, operating guide, project walkthrough, and preprint are now delivered in the [documentation set](../README.md). The design rationale below is retained; completed multi-session case studies remain collection work rather than being implied by the derived walkthrough.

| Document or continuing work | Reader's purpose | Concrete content |
|---|---|---|
| [System README](../../README.md) | Understand what the system does and where to begin. | Lead with prepared functional understanding and its reuse; show one small actual project example, installed entrypoints, current capability boundaries, and links to deeper material. |
| [First-session guide](../guides/getting-started.md) | Complete one useful operation and recognize its result. | Use the actual installation and project/intake operations; show the resulting map, a meaningful relationship read, and where a contribution is retained. Keep command output tied to a named source version. |
| [Community module-author guide](../guides/extending-metaform.md) | Add a capability using the implemented contract. | Use template and helloworld to explain declarations, settings, Context, CLI/MCP exposure, store access, owned tasks, events, instructions, and packaging. Show what is supplied by the chassis rather than recreating it in each example. |
| [Reading an Inference Metaform](../guides/reading-a-metaform.md) | Read the functional graph without mistaking it for a code hierarchy. | Explain receiver, purpose, provider, Function/Encounter, reified join, subtype containment, names, ancestry, and refs using one annotated part of the actual project map. |
| [Operating guide](../guides/working-with-metaform.md) and [project walkthrough](../examples/project-walkthrough.md); further recorded task cases | Apply an operation through existing understanding. | Pair an original request with its grounded context, actual operation, result, and newly reusable knowledge. Keep examples focused on tasks such as explanation, criticism, extension, refactoring, and formation of non-code artifacts. |
| Completed case studies | Follow preparation and reuse through real work. | Build from the original traces in [EXAMPLES_TO_COLLECT.md](EXAMPLES_TO_COLLECT.md), including measured records where supplied. Show what remained reusable and what required fresh inference. |

### A README that demonstrates rather than advertises

The opening should give a concrete contrast: an agent can know the files yet still need to reconstruct what the workpiece is for; the Inference Metaform supplies retained functional understanding. Follow that immediately with an actual receiving-purpose relationship and one task that uses it. This communicates the mechanism without reducing it to a memory product or relying on promotional claims.

The full reference should remain the place for the detailed semantic account. The README should not attempt to compress every mechanism into an all-purpose paragraph, because that would erase precisely the distinctions the reference preserves.

### A first session with one real benefit

The delivered first-session guide stops at a recognizable result: a reader has examined an actual relationship and knows how it can orient work. It need not stage a fictional autonomous workflow or introduce an unconstructed lexicalizer as though it were an installed command.

The delivered guides distinguish recorded project material, local command exercises, and derived illustrations. Installation, host registration, server probing, and installed-skill behavior should be described according to the exercised path. The [implementation map](IMPLEMENTATION_MAP.md#supporting) identifies the present boundaries, including planned verification functionality.

### A module-author guide centered on shared facilities

This is the strongest immediate companion to the reference because the community extension mechanism is implemented. A reader should see a declaration produce usable surfaces and should understand when to use context, settings, store access, event delivery, and separately owned work. The guide should preserve the actual scheduling and lifecycle rules instead of deriving them from a broad graph label.

The delivered guide also makes an absence legible: a lexicalization or criticism producer can be new work even though its module contract, storage, settings, and execution facilities already exist. That distinction helps contributors build on the chassis rather than recreate it.

<a id="order"></a>
## 5. A practical order of work

The **README/first-session pair** and **module-author guide** are now delivered, together with the reader and operating guides and the preprint. The shared [project walkthrough](../examples/project-walkthrough.md) uses actual graph records and explicitly labeled derived tasks. The next case-study work is to retain complete original preparation-and-reuse episodes, following [EXAMPLES_TO_COLLECT.md](EXAMPLES_TO_COLLECT.md).

For tooling, the **knowledge-participation explanation** and **purpose-aware memory view** build directly on existing operations. They can make current behavior understandable without waiting for new inference producers. A task-preparation view should be built with the actual lexicalization producer so the visible substitutions and knowledge contributions describe the operation that really occurred.

The **reuse report** can begin as an authored report over original task records. Its useful associations can then inform later instrumentation, rather than designing a comprehensive telemetry architecture before seeing what helps readers follow the work. Likewise, a relationship comparison can begin with an actual refactor or transformation and expose where a tool would remove repetitive work.

Cross-workpiece transfer is a broader direction. It is most useful when tied to a concrete contribution that another project can use and to the differences that matter there. The aim is more reusable understanding, not another layer of infrastructure whose purpose is detached from an actual receiving entity.

These proposals can be pursued independently. Their common criterion is practical usefulness to a person or agent working through the Inference Metaform: show the prepared meaning, show its participation in the task, and preserve the new understanding produced by the work.

---

[Technical reference](REFERENCE.md) | [Implementation map](IMPLEMENTATION_MAP.md) | [Examples to collect](EXAMPLES_TO_COLLECT.md)
