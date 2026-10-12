# Metaform — Superseding Product Requirements

**Status:** Governing product requirements
**Effective date:** 2026-09-18
**Authority:** This document supersedes all previous product requirements, requirement registers, implementation plans, architectural proposals, recovered requirement inventories, and conflicting implementation descriptions.

Older documents, code, tests, audits, plans, examples, and archived specifications remain useful as evidence, history, semantic source material, migration input, and remediation guidance. They do not create additional product requirements beyond those stated here.

The current Canonical Intake and other explicitly maintained authored workflows remain authoritative for the behavior of those workflows. This document governs how the product preserves and executes them; it does not rewrite their authored semantics.

## 1. Interpretation and implementation freedom

### REQ-001 — This document is the complete requirement set

Implementation and remediation shall use the requirements in this document as the normative product contract.

Do not mine older documents for additional requirements.

Do not treat an old implementation, old test expectation, old plan, historical proposal, generated analysis, or prior requirement inventory as an additional requirement unless its behavior is expressly retained here.

### REQ-002 — Requirements describe outcomes and invariants

A requirement defines behavior, ownership, compatibility, semantics, or an observable result.

Implementation details not constrained here remain engineering choices.

Existing implementation details may be retained when they satisfy these requirements. They may be replaced when another implementation satisfies them more cleanly.

### REQ-003 — Open implementation choices do not block unrelated work

Where this document intentionally leaves a mechanism unspecified, implementation may proceed using the simplest adequate design consistent with the stated requirements.

Do not stop remediation merely because an old document contains an unresolved implementation choice.

Do not invent product semantics to close an ambiguity.

If a choice affects an irreversible data interpretation, authored semantic meaning, or externally visible compatibility contract, preserve the existing evidence and choose a reversible implementation until that meaning is resolved.

### REQ-004 — No implementation self-ratification

Existing code, tests, schemas, migrations, packaging structure, or passing demonstrations cannot redefine a requirement merely because they already exist.

Verification tests must establish required behavior rather than encode an accidental implementation as the requirement.

---

# 2. Product purpose and semantic foundation

### REQ-010 — Project understanding is reusable working context

Metaform records functional understanding of an artifact so later people, workflows, and agents can reason from that prepared understanding rather than reconstructing it from raw evidence each time.

That understanding remains revisable and attributable.

### REQ-011 — Artifact independence

Metaform shall operate on software and non-software artifacts, including projects within larger repositories, documents, images, collections, designs, contracts, stories, and other source material.

The selected artifact and its source boundary remain explicit.

### REQ-012 — Types and artifact realizations remain distinct

A namespace Type expresses reusable functional meaning.

The actual artifact account expresses how that Type is realized in the selected artifact.

Neither representation silently replaces the other.

### REQ-013 — Namespace addresses are meaningful identities

Namespace addresses are stable semantic addresses, not opaque storage keys.

Namespace placement narrows functional meaning from general to specific.

Readable names may be rendered from namespace addresses, but presentation text must not replace stored identity.

### REQ-014 — Elements and Entities remain distinct concepts

An Entity is an Element that may contain Elements.

Not every Element is an Entity.

The Type of an Entity and the Type of its Defining Element need not be identical.

### REQ-015 — Encounter meaning belongs to the relationship

A Receiving Element or Entity owns its relationship to a Providing Element.

The relationship retains:

* the Receiving Element/Entity;
* its Operative Purpose;
* the Providing Element;
* the Encounter Function applicable to that encounter;
* applicable relationship information and references.

A provider may participate in multiple encounters with different Encounter Functions.

A universal single Element-level Encounter Function shall not replace encounter-specific meaning.

### REQ-016 — Joins remain owned and directly addressable

A join belongs to its Receiving Element/Entity's namespace object.

It has stable identity within that ownership context and may be directly referenced, revised, used as inference context, receive knowledge or memory, and participate in provenance.

A join need not become an independent namespace object merely to make it addressable.

### REQ-017 — Universal object shape remains extensible

Namespace objects expose their namespace identity, naming information, and owned typed joins.

Modules may define additional join types and content without forcing every join into one closed feature schema.

Unknown but valid extension content must survive reads, edits, copying, relocation, and export.

### REQ-018 — Current namespace evolution is preserved

`asset` supersedes the former current use of `media`.

The namespace supports an `entity` Type trunk.

Historical material using earlier addresses remains readable and attributable.

Exterior or outside participants must remain representable, but this requirement does not prescribe a new universal trunk name for them.

---

# 3. Intake and functional understanding

### REQ-020 — Intake is an authored workflow

Canonical Intake executes through the normal workflow system and shared chassis services.

It is not implemented through a second special-purpose execution engine.

### REQ-021 — Canonical Intake semantics are preserved

The maintained Canonical Intake governs its own terminology, procedure, response protocol, decomposition, combining/annealing behavior, and completion semantics.

The intake glossary is scoped to intake and shall not be forced onto unrelated feature data.

### REQ-022 — Intake begins coarse and remains extensible

The initial account identifies useful functional reference positions without attempting to reproduce every implementation detail.

Later operations may deepen an Element, join, branch, or bounded region.

### REQ-023 — Annealed positions remain addressable

Elements combined away from the active coarse shape remain addressable as inactive or combined positions where required for memory, knowledge, references, and historical provenance.

### REQ-024 — Actual artifact evidence remains available

Reasoning that requires source evidence must receive the actual applicable evidence, not merely names or generic Type descriptions.

Source identity and project context remain retained.

### REQ-025 — Native and Latent reasoning retain separate provenance

Native reasoning grounds the functional account in the artifact.

Latent reasoning may receive the complete resulting Native account while remaining independent of direct repository implementation context.

Their outputs remain separately attributable.

### REQ-026 — Structural corrections are explicit revisions

A proposed correction does not silently rewrite the current foundation.

Applying a correction records the previous state, new state, reason, evidence, and resulting foundation revision.

---

# 4. Standalone chassis and true modularity

### REQ-030 — The chassis is independently operable

The chassis is a complete standalone product.

It must start and provide chassis administration and shared services when:

* all feature modules are disabled; and
* all feature modules are physically absent.

This applies to installed and executable-wheel operation.

Feature absence may remove feature capabilities. It must not remove the chassis.

### REQ-031 — The chassis is the smallest adequate shared substrate

The chassis owns only shared infrastructure required for independently implemented modules to cooperate:

* module discovery and lifecycle;
* module compatibility and contribution ownership;
* settings persistence and configuration presentation;
* contextual CLI framework;
* project/work context;
* assignment and nonce resolution;
* generic synchronous and asynchronous execution;
* event delivery;
* common object/reference access;
* generic durable storage;
* generic revision and provenance machinery;
* generic portable-runtime bootstrap/entrypoint support;
* chassis administration.

Feature-specific behavior does not belong in the chassis.

### REQ-032 — Every feature is implemented in a module

Every removable feature is implemented in a module using the common module contract.

This includes shipped and optional features such as workflow behavior, knowledge and memory operations, artifact history, distribution building, MCP, web, terminal integrations, harness adapters, and other feature functionality.

A module that merely forwards to a feature engine embedded in the chassis does not satisfy this requirement.

### REQ-033 — Every feature module follows the canonical template contract

Every shipped feature module is derived from the canonical module template in structure and public-contract use.

"Derived" means it follows and demonstrates the same extension contract; it does not mean it imports or depends on the showcase/template module at runtime.

Each derived module must remain independently usable when the template demonstration module is absent.

### REQ-034 — Modules are self-contained

A module may be:

* one Python file; or
* one contained Python package/subfolder beneath `modules/`.

Feature implementation, helpers, owned resources, feature configuration declarations, and feature-specific dependencies remain within the feature's module boundary or are explicitly declared dependencies.

### REQ-035 — Modules load from three places in priority order

An installed Metaform loads modules from three places. In priority order:

1. System: the modules bundled in and installed from a wheel. These are the system modules. They live in the installed package.
2. User: modules that can be used by any project. They live in the global data root's `modules/` folder.
3. Project: modules that only load from the active selected repo. They live in that repo's `.metaform/modules/` folder. The chassis's project selection decides which repo is active, not the working folder.

`.metaform` is a data folder. It is not the place where the core modules live.

A module with the same name as a higher-priority module can only enable if the higher-priority module is disabled in the chassis.

The chassis can disable modules. The authoritative dynamic disable policy is the text file `modules/disabled` in the global data root. Each entry names the place and the module, and a Project entry also names the project. Disabling one copy leaves same-name copies elsewhere untouched.

Entries in that blacklist identify modules that must not load.

An absent blacklist entry means the module is not disabled by that policy.

The module catalog lists the active copy of each module and every same-name copy it holds back, with their places.

A wheel is not so much a higher authority as a completely separate one.

Existing installed state must be preserved when migrating from earlier locations.

### REQ-036 — Shipped and community modules use the same contract

Built-in, shipped, optional, and community modules use the same public extension mechanism.

The chassis must not contain privileged feature-specific loading, dependency, command, configuration, or distribution behavior keyed to built-in module names.

### REQ-037 — Module discovery and activation are distinct

Discovery identifies available modules and enough metadata to determine whether activation can be attempted.

Activation executes module code and acquires runtime resources.

Information that must be known before importing potentially incompatible code must be safely discoverable before that import. The representation of that information is an engineering choice and does not require a separate mandatory manifest.

### REQ-038 — Module lifecycle is owned and reversible

Activation registers all contributions and owned runtime resources as one module lifecycle.

Failed activation withdraws partial contributions.

Unload/deactivation withdraws commands, settings surfaces, help, subscriptions, tasks, processes, integrations, and other active contributions owned by the module while preserving durable settings, objects, history, and provenance.

Repeated unload/reload must not accumulate duplicate contributions or stale owned resources.

### REQ-039 — Module failures are isolated

A failed, incompatible, missing, or disabled module must not make chassis administration or unrelated compatible modules unusable.

### REQ-040 — Modules interact through public contracts

Feature cooperation uses chassis public services, module operations, managed object references, or the shared event system.

One module must not require another module's private implementation, concrete internal store, private engine class, or source layout.

### REQ-041 — Public module-to-module invocation exists

A module may discover available capabilities and invoke another module's public operation without importing its private implementation.

The call preserves caller/callee ownership, current project/work context, provenance, and absence/unavailability results.

### REQ-042 — Platform limits belong to modules

The Python chassis itself remains usable on supported Linux, macOS, and Windows environments.

Modules own and declare narrower platform restrictions and platform-specific dependencies.

An incompatible module is skipped without destabilizing the chassis.

Declared compatibility and actually verified platform support remain distinguishable.

---

# 5. Public module service contract

### REQ-050 — Stable public services

Modules have stable documented access to shared services, including the established:

```python
from metaform import settings, event, cli, data
```

and the public work, module, object/reference, execution, and other chassis services required by the extension contract.

### REQ-051 — Public imports do not create competing runtimes

Importing a public facade does not independently create a database, application, runtime, listener, process host, or project state.

Services resolve the active execution context.

### REQ-052 — Context follows operations

Project, module, operation, assignment, nonce, producer, step, and working-folder context are carried explicitly through the public execution path where applicable.

Concurrent operations must not inherit one another's mutable context.

### REQ-053 — Both synchronous and asynchronous access are supported

Shared services needed by module work, including universal object and owned-join access, provide appropriate synchronous and asynchronous access paths.

Async callers shall not be forced to bypass the public service or block the shared execution loop to use the actual object model.

### REQ-054 — Feature logic has one owning operation

CLI, MCP, web, workflow, event, or other adapters invoke the same owning public operation rather than implementing parallel business logic.

---

# 6. Settings and configuration

### REQ-060 — Modules own their setting definitions

Each module declares the settings it owns, including keys, types, defaults, descriptions, and applicable setting-specific constraints or timing.

The chassis generically registers, persists, displays, resets, and resolves those declarations.

### REQ-061 — Configuration has one authoritative external root

Durable Metaform configuration is stored in one unified external state location for the selected Metaform root/environment.

Configuration is not owned by an extracted runtime directory, installed package directory, or wheel path.

### REQ-062 — Missing configuration hydrates from module declarations

When a module or declared setting has no persisted configuration, the missing configuration is created from the module's declarations/defaults.

This works during direct-wheel execution.

No permanent installation or manually copied default configuration is required.

### REQ-063 — Hydration is additive and non-destructive

Hydration supplies missing values.

It does not overwrite existing compatible user values, glued baselines, unknown compatible fields, or settings introduced by another compatible release.

Repeated hydration is safe.

### REQ-064 — Configuration survives module absence

Disabling, unloading, removing, and later restoring a module preserves its saved values and glued state.

Its configuration surface disappears when the module is unavailable and returns when the module returns.

### REQ-065 — Glued values are user-owned baselines

A user may pin the effective value of a setting as a baseline.

Ordinary reset restores unglued values to declared defaults while retaining glued values.

Changing a module default does not silently replace a glued value.

### REQ-066 — Installed and portable execution share configuration intentionally

For the same selected Metaform state root, compatible installed and direct-wheel surfaces resolve the same authoritative configuration.

Wheel location, extraction path, or compatible minor/patch version must not silently create an unrelated configuration universe.

---

# 7. Contextual and uncluttered user interface

### REQ-070 — Surface economy is a governing UX principle

Metaform presents a polished, understandable, low-clutter surface appropriate to the user's current context.

Complexity remains available through discovery and inspection rather than occupying the primary working surface.

### REQ-071 — Progressive disclosure

The chassis root presents chassis status and the small set of actions needed to administer or enter available capabilities.

Feature-specific commands are primarily exposed inside their owning module context.

Assignment-specific operations are exposed inside assignment context.

Advanced diagnostics, raw IDs, provenance detail, and internal representations remain inspectable without dominating ordinary use.

### REQ-072 — Module ownership remains visible

Users and agents can determine which module owns a capability, command, setting, operation, or UI contribution.

This does not require flattening every module's commands into the chassis root.

### REQ-073 — Complete CLI

Every functional operation has a CLI route with the required module present.

Web and MCP are optional additional interfaces and are not prerequisites for functional completion.

### REQ-074 — Context drives the CLI

Entering a module may replace the chassis root command/menu surface with the module's contextual surface.

The active context persists across separate invocations using the working-folder discovery/binding mechanism.

Exiting module navigation restores the chassis surface without erasing durable work.

### REQ-075 — Assignment context drives the work surface

Entering or resolving an assignment nonce exposes the applicable module/workflow surface, actual current instructions, prompt, selected context, memory/knowledge addresses, required submission header, status, and lifecycle operations.

### REQ-076 — Navigation exit and work finalization remain distinct

Leaving a contextual menu does not silently complete or abort durable assigned work.

Submission, step progression, completion, abort, and navigation exit retain distinct meanings.

### REQ-077 — Help is generated from live contributions

Help, command discovery, completion, status, and actual invocation use the same active capability/context resolution.

Module help and setting descriptions remain owned with the module rather than copied into a second manually maintained feature catalog.

### REQ-078 — Interactive and non-interactive use are equivalent in capability

Human-friendly interactive presentation may be provided.

Every operation that can be fully specified must also work non-interactively with supplied arguments or structured input.

Structured output remains separable from diagnostics.

### REQ-079 — Configuration UI remains concise

Provide a polished keyboard-driven settings/module-management surface supporting inspection, editing, enable/disable, reset, glue, staged changes, save/discard, and contextual help.

The historic BIOS-style reference describes desired usability, not a required UI framework.

---

# 8. Work identity, agents, nonce, and MCP

### REQ-080 — Work identity is durable and transport-independent

A nonce identifies assigned work and its durable context.

Process IDs, transport connections, working directories, client names, or server instances are operational metadata and do not replace work identity.

### REQ-081 — Assignment delivery is exact

Assigned work delivers the actual stored prompt/instructions and resolved context.

The orchestrator may supply the nonce and Metaform invocation without paraphrasing the assignment.

### REQ-082 — Submission uses the assignment header

The assignment supplies a required submission header.

Submission verifies that the returned work is associated with the intended assignment.

This is a routing/integrity mechanism, not a generic semantic answer-quality gate.

### REQ-083 — Working-folder discovery is durable

The working-folder marker resolves the durable assignment and project/workfolder context across independent CLI invocations.

The marker is a discovery reference, not the authoritative work record.

### REQ-084 — MCP uses the same work identity

The MCP adapter is a removable module.

For transports supporting request headers, the assignment nonce is carried through the designated Metaform header approach and resolved through shared assignment/context services.

Where a transport cannot express an HTTP-style header, the adapter must carry the same nonce explicitly without replacing it with transport/process identity.

### REQ-085 — One MCP process may serve multiple assignments

A shared MCP server can interleave work for multiple nonces.

Each request resolves its own assignment, project, workfolder, producer, and context.

### REQ-086 — CLI and MCP deliver the same work

CLI and MCP expose the same assignment, actual prompt, references, selected knowledge/memory, lifecycle, and submission contract.

MCP does not replace CLI completeness.

### REQ-087 — Harness participation is vendor-independent

Metaform supports both:

* launching a configured harness; and
* being operated from inside an already-running harness.

Codex and Claude are required demonstrations, not chassis dependencies.

A deterministic local fixture remains available for protocol/mechanical testing.

---

# 9. Execution, jobs, and event cooperation

### REQ-090 — Modules may be synchronous, asynchronous, or both

The execution system supports both forms through the shared runtime.

Agent work is asynchronous.

### REQ-091 — Long-running work does not block unrelated operations

Starting agent or other background work returns a durable trackable receipt.

Independent status, configuration, CLI, object reads, and other operations remain usable while work is pending.

### REQ-092 — Work survives initiating client exit where required

Work and continuation state needed by a later CLI/MCP invocation are durably retained.

A workflow must not depend solely on the lifetime of the client process that started it.

### REQ-093 — Background work has explicit ownership

Tasks, subprocesses, workers, event deliveries, and other background activity used by shipped modules are owned by a module/operation/runtime lifecycle.

Supported background work may not silently escape that ownership and continue writing under a completed producer.

### REQ-094 — Cancellation state is truthful

Requesting cancellation is distinct from work having actually stopped.

Success, failure, requested cancellation, completed cancellation, and interruption remain distinguishable.

### REQ-095 — Event bus is shared infrastructure

Modules publish and subscribe through the chassis event service.

Events retain publisher, subscriber execution attribution, project/work identity, affected managed references, and delivery outcomes.

### REQ-096 — Event request/response is complete for terminal outcomes

The demonstrated asynchronous request/response pattern returns a terminal outcome through the same cooperation contract for success, failure, and cancellation.

### REQ-097 — Events do not become a second workflow engine

Events announce or deliver cooperative activity.

Authored workflow progression and synchronization remain owned by the workflow feature.

---

# 10. Data, revision, and provenance

### REQ-100 — One common object/reference model crosses module boundaries

Public operations, events, jobs, workflow bindings, adapters, and export retain managed object/owned-join identities and revisions.

Disconnected feature-specific dictionaries do not replace those references where object identity is required.

### REQ-101 — Reads used for reasoning retain exact revisions

When content is supplied to an inference operation, the exact object/join/knowledge revisions actually delivered are recorded.

An identity-only reference is insufficient when the consumed content can later change.

### REQ-102 — Inference provenance is mandatory for inference

An inference result records:

* producing operation/run;
* prompt definition/revision;
* exact rendered prompt;
* variables and object/value bindings;
* exact dynamically retrieved input references and revisions actually consumed;
* relevant selected layers/context;
* submitted answer;
* produced outputs;
* causal relationship to prior producing occurrences.

A generic activity log or producer label is insufficient.

### REQ-103 — Non-inference provenance remains truthful

Authored content, imports, deterministic transformations, manual edits, migration, and other non-inference creation retain their actual origin.

They are not given fictional prompts or agent inference histories.

### REQ-104 — Producing occurrence and content identity are distinct

Two operations that independently produce identical content remain independently attributable producing occurrences.

Content deduplication must not merge their causal histories.

### REQ-105 — One-reference provenance inspection

Given an output, knowledge contribution, memory, workflow answer, or owned-join reference, callers can retrieve its producing evidence and follow its actual inputs backward.

Prior produced inputs can be recursively followed to their own producing prompts and evidence.

### REQ-106 — Current mutable state never rewrites historical input

Editing, updating, hiding, replacing, or deleting current memory, rules, prompts, knowledge, or source material does not retroactively change what an earlier run consumed.

### REQ-107 — Object identity survives physical relocation

Copying, moving, splitting, unifying, exporting, or importing storage preserves object/join identity, revision, project ownership, and provenance.

Physical database placement does not redefine semantic identity.

### REQ-108 — Storage placement is configurable

Metaform may place namespace-owned contributions in unified or split storage and at global or project scope as configured.

Routing is physical organization of the same objects and joins.

Changing placement must actually populate the requested destination rather than merely continuing to resolve an old copy.

### REQ-109 — Durable writes are recoverable

Database, configuration, payload, import, relocation, and portable-restoration operations are coordinated so interruption does not silently replace complete valid state with partial state.

Retries must be deterministic and preserve prior valid information.

### REQ-110 — Existing data is preserved

Migration from earlier Metaform representations preserves source records, identities, prompts, answers, relationships, and provenance wherever available.

Unmapped or conflicting material remains visible rather than being silently fabricated, discarded, or treated as agreement.

---

# 11. Knowledge, selection, and agent memory

### REQ-120 — Knowledge attaches locally

Knowledge and inference layers may attach to namespace Elements and owned joins.

Attachment location and causal input dependencies are separate concepts.

### REQ-121 — Knowledge selection follows the established mask rule

At each object:

```text
effective_selection =
    (incoming_selection & layer_select_mask) | layer_select
```

The project supplies initial selection.

Objects default to no added local selection and pass inherited selection through unless masked.

Selection propagates through the namespace according to the established trunk-to-leaf behavior.

### REQ-122 — Selection applies to all context paths

Direct object context, property/provider context, workflow context, MCP reads, and other inference assembly paths observe the same applicable selection rules.

An excluded layer cannot leak into the prompt through a secondary property/provider path.

### REQ-123 — Unsupported selection remains explicit

If stored selection data cannot yet be executed faithfully, retain it and report that executable interpretation is unresolved.

Do not silently substitute broad project defaults.

### REQ-124 — Causal visibility is dependency-based

Hiding a source actually used to produce knowledge hides the dependent inference from the active view/context, including transitive dependent inference.

Stored historical content and provenance remain retained.

Restoring one source must not override an independently chosen hidden state or another still-hidden dependency.

### REQ-125 — Generated knowledge records its actual sources

Generated knowledge records the graph nodes, properties, prior knowledge, revisions, and other context actually included in its producing prompt.

Available but unused information is not recorded as consumed input.

### REQ-126 — Agent memory is a mutable localized knowledge graph

Agent memory is a normal module-provided knowledge capability using existing namespace Element and owned-join addresses.

Agents can:

* create;
* read;
* search;
* update; and
* delete

localized memory.

Memory is not merely a chronological conversation log.

### REQ-127 — Memory preserves revision history

Updating or deleting current memory changes current availability while preserving historical revisions consumed by previous work.

### REQ-128 — Memory uses normal public surfaces

Memory CRUD/search is available through CLI and, when those adapters are installed, MCP and web.

All surfaces use the same underlying memory operations, references, context, and provenance.

---

# 12. Rulebook

### REQ-130 — Rules belong to operations

Specific authored rules may be attached to the operation, task, workflow, or process they govern.

### REQ-131 — Rule content remains authored content

The platform preserves concise rules, explanatory material, examples, and authored teaching distinctions supplied by the rule definition.

The platform does not invent generic output restrictions merely because a rule exists.

### REQ-132 — Rules are inspectable and editable

Users can discover the rules applicable to an operation, inspect their current and historical revisions, and edit them through common object/workflow interfaces.

CLI access exists independently of web.

### REQ-133 — Operations apply their applicable rules

A rule claimed by an operation must actually participate in that operation according to its authored behavior.

This does not establish a universal retry, rejection, approval, or semantic-scoring mechanism.

### REQ-134 — Issued rule revisions are retained

Work retains the exact rule revisions supplied when it was issued.

Later edits affect later work without rewriting earlier instructions.

---

# 13. Workflows and authoring

### REQ-140 — Workflows preserve authored intent

Import, specialization, execution, conversion, and editing preserve authored sequence, branches, loops, waits, roles, handoffs, tool use, completion conditions, and response routing.

Do not add generic approvals, retries, or output gates that were not part of the authored workflow.

### REQ-141 — Serialization and semantic conversion are distinct

Serializing an already-native workflow and inferring executable meaning from an external workflow are different operations.

Both preserve the original source and record transformations separately.

### REQ-142 — Canonical workflow representation preserves meaning

Supported XML, structured dictionary/JSON, and Markdown representations preserve execution meaning, object bindings, ordered/repeated content, attributes, mixed content, schemas, and authored text needed by the workflow.

XML mapping uses ElementTree.

Exact byte-for-byte whitespace/comment fidelity is not required unless an interface explicitly promises it.

### REQ-143 — Context remains object-bound

Workflow prompts store and resolve references to namespace objects, joins, knowledge, variables, and prior outputs rather than reducing those identities permanently to copied text.

Rendering does not destroy the underlying binding.

### REQ-144 — Lexicalization is explicit

Lexicalization is an inspectable operation that binds workflow language to project objects/context while preserving the source definition and recording the resulting revision.

Import alone does not silently lexicalize a workflow.

### REQ-145 — Issued prompts are exact snapshots

When a step is issued, retain the exact prompt, selected context, bindings, references, revisions, applicable rules, selected knowledge, and submission header actually delivered.

### REQ-146 — Workflow revisions and runs are independent

Editing a workflow or prompt creates a new definition revision.

Existing or historical runs retain the revisions they actually used.

### REQ-147 — Replay may reuse valid prior work

A workflow may resume from an edited point while reusing prior retained outputs where the authored workflow semantics permit it.

The earlier run remains intact.

### REQ-148 — Human waits remain human waits

If an authored workflow waits for user input, approval, feedback, or another human-directed interaction, an agent must not silently manufacture that response.

### REQ-149 — Workflow execution is CLI-complete

With required feature modules present, the entire workflow lifecycle is possible through CLI alone:

* discover;
* import/prepare where applicable;
* author/edit where applicable;
* start;
* inspect assigned context;
* supply required input;
* retrieve prompt/context;
* submit;
* advance;
* inspect outputs/provenance;
* continue;
* complete or abort.

Web and MCP may provide alternative interfaces but are not required.

### REQ-150 — Workflow upload preparation remains module-owned

Workflow-specific preparation and packaging behavior belongs to the workflow module and cooperates with generic distribution/runtime services.

---

# 14. Artifact history and portability

### REQ-160 — Artifact boundaries are consistent

Baseline capture, change capture, reconstruction, comparison, and export operate on the same intended artifact boundary.

Relevant tracked, untracked, ignored, binary, added, removed, renamed, and applicable metadata are preserved as required by that selected boundary.

### REQ-161 — Navigation markers are not artifact edits

Metaform's temporary context, nonce, discovery, runtime, or navigation markers do not become artifact modifications or reconstructed project files.

### REQ-162 — Origins and variants remain distinct

A retained source origin is not overwritten by later work.

Multiple experiments against one origin remain sibling variants unless an explicit operation establishes a new origin.

### REQ-163 — Reconstruction works without the original repository

Exported history includes enough baseline and change material to reconstruct supported selected artifacts using Python without requiring the originating repository or Git.

### REQ-164 — Portable continuation includes pending physical work

A pending assignment's required working files, including dedicated workfolder content, staged inputs, generated outputs, and applicable binary files, travel with portable continuation when needed by future execution.

A nonce and prompt without their required physical inputs are not a complete continuation.

### REQ-165 — Import preserves divergent history

When an import would destroy distinct existing history or provenance, preserve both histories and expose their identities.

---

# 15. Executable wheel and offline delivery

### REQ-170 — The wheel is an executable Metaform delivery artifact

Metaform ships a standards-compatible `.whl` which is also intentionally supported as a directly executable delivery artifact.

A supported invocation is:

```text
python /path/to/metaform.whl
```

The installed command and `python -m metaform` expose the same functional CLI contract.

### REQ-171 — Direct wheel use does not require permanent installation

The executable wheel may extract or prepare an owned local runtime when necessary.

The user or hosting agent is not required to perform a permanent package installation before running it.

### REQ-172 — Cold offline execution is required

The uploaded wheel must run in a supported execution environment with:

* no Metaform installation;
* no source checkout;
* no internet access;
* no prepared Metaform dependency/runtime cache.

It carries the code, selected modules, dependencies, resources, defaults, help, and workflow assets required by the selected delivered capability.

### REQ-173 — Hosted-agent execution is a primary delivery case

The wheel must be uploadable to execution environments such as ChatGPT, Anthropic-hosted agent environments, and comparable Python execution environments and be operable by the hosting agent using the available process-execution surface.

The agent can obtain assigned context, perform reasoning in its existing host context, and submit work through Metaform without Metaform requiring a separate remote inference API from inside that environment.

### REQ-174 — Runtime preparation is isolated

Temporary/extracted runtime content is separate from durable configuration, project data, history, and continuation state.

Rebuilding or deleting the prepared runtime does not erase durable state.

Running a wheel does not replace or downgrade an installed Metaform distribution or its dependencies.

### REQ-175 — Selected modules mean selected implementations

A wheel built with selected modules contains the selected feature implementations, their owned resources, and required dependencies.

A zero-feature-module wheel contains the chassis and does not secretly carry excluded feature engines.

### REQ-176 — Packaging derives dependencies from ownership

Feature dependencies are owned and declared by their feature modules.

The chassis does not select optional dependencies by hardcoded built-in module names.

### REQ-177 — Native/platform dependencies produce accurate compatibility

Selected native libraries, extension modules, executables, and platform-specific resources participate in compatibility determination and artifact tagging.

A wheel containing platform-specific content must not claim universal pure-Python compatibility.

---

# 16. Same-major compatibility and installed-system integrity

### REQ-180 — Same-major compatibility is bidirectional

Within a major release series, supported minor/patch versions remain mutually compatible at the public and persisted-data boundaries.

For the 1.x series specifically:

* an older 1.x wheel can operate against a newer 1.x installed/state surface;
* a newer 1.x wheel can operate against an older 1.x installed/state surface.

### REQ-181 — Compatibility is behavioral, not version-string acceptance

Compatibility means the supported operation can actually read and write the selected state without damaging the ability of the other compatible 1.x surface to continue operating.

### REQ-182 — Older writers preserve unknown compatible data

When an older same-major implementation updates content it understands, it preserves additional compatible fields, settings, references, revisions, and provenance that it does not interpret.

### REQ-183 — Minor/patch evolution is non-destructive

A minor/patch release does not require destructive one-way migration, forced installation upgrade/downgrade, state reset, or substitution of an empty state root to preserve same-major usability.

A change that cannot preserve the required compatibility belongs to a major-version boundary.

### REQ-184 — Wheel execution does not corrupt installation state

Running an uploaded or local wheel must not replace, downgrade, modify, or corrupt an existing installed Metaform package, its unrelated dependencies, entrypoints, configuration, or data.

Normal user-requested changes to shared compatible Metaform state remain allowed.

### REQ-185 — Runtime code origin is deliberate

Portable execution must not accidentally combine implementation files or dependency versions from an unrelated installed Metaform copy.

A compatible shared runtime may be reused only deliberately; otherwise the portable runtime remains isolated.

---

# 17. Optional MCP, web, and terminal modules

### REQ-190 — Web is optional

The web workbench is a removable module.

Removing it leaves CLI, data, workflow, memory, provenance, and chassis administration functional.

### REQ-191 — Web uses the same operations and objects

The web interface presents and invokes the same module operations, work identity, object references, provenance, and durable state used by CLI and MCP.

It does not construct a private workflow/data execution path.

### REQ-192 — Web presentation is polished and uncluttered

The web surface emphasizes current project context and primary actions.

Detailed IDs, raw fields, diagnostics, causal history, and advanced controls are available through inspection rather than permanently occupying the primary view.

Graph presentation shows actual semantic objects and relationships rather than invented filler or confidence decorations.

### REQ-193 — Web implementation technology is not a product invariant

The web module may use an appropriate asynchronous Python web stack.

No particular framework is required by this specification.

The chassis must remain independent of that stack.

### REQ-194 — One global web instance may serve tracked projects

Where the web feature is enabled, it may provide one configured service instance for the Metaform state root and navigate among tracked projects without creating independent product state per listener.

### REQ-195 — Authentication configuration belongs to the web module

Web access policy, token access, binding, and optional trusted-environment authentication bypass are module-owned configuration.

Any intentionally unauthenticated non-loopback deployment is an explicit deployment choice, not an implicit default.

### REQ-196 — Browser terminal functionality is optional and separate

A browser terminal/coding-agent/shell capability may be supplied by a separate module and must not impose its platform dependencies on the chassis.

---

# 18. Developer experience and documentation

### REQ-200 — Every shipped module has a developer README

Each module's documentation explains:

* purpose;
* canonical template derivation;
* entry declaration;
* imported public services;
* operations and return behavior;
* CLI surface;
* settings and defaults;
* generated configuration;
* event publication/subscription;
* sync/async behavior;
* data/object ownership;
* revision and provenance behavior;
* lifecycle and cleanup;
* module dependencies;
* supported platforms;
* module-owned resources;
* nonce/work context where applicable;
* installed execution;
* direct-wheel execution;
* runnable demonstration.

### REQ-201 — The template demonstrates the real current contract

The standalone template demonstrates actual namespace objects, owned joins, exact references, revisions, inference/authoring provenance, settings, events, sync/async operations, jobs, assignments, headers, and module inspection.

It must not teach an obsolete compatibility record model as though it were the primary current object model.

### REQ-202 — Three teaching modules remain

Ship:

1. one independently usable all-services template/showcase;
2. one event requester derived from that pattern; and
3. one harness responder derived from that pattern.

The latter two demonstrate a nonblocking request and eventual response through the same shared event service.

Neither depends on the showcase module being installed.

### REQ-203 — Documentation exposes actual ownership

Developer documentation must make it possible to determine whether behavior is chassis-owned or module-owned.

Documentation must not present two competing current module contracts.

---

# 19. Verification and product quality

### REQ-210 — Verify externally observable behavior

Acceptance is based on actual product behavior and retained evidence, not test count.

Tests must exercise public paths and real artifact boundaries.

### REQ-211 — Semantic and mechanical correctness are distinct

Successful parsing, persistence, transport, or workflow completion does not by itself prove the semantic result satisfies its authored procedure.

Where semantic correctness matters, review the actual retained prompt/context/answer.

### REQ-212 — Fixtures and real providers are labeled accurately

A deterministic fixture demonstrates mechanics.

A local offline simulation demonstrates its specific environment.

An actual Codex, Claude, ChatGPT-hosted, Anthropic-hosted, or other provider execution demonstrates only the environment and path actually exercised.

Do not substitute one category for another in status reporting.

### REQ-213 — Zero-module acceptance is required

Verify installed and direct-wheel operation with all feature modules disabled and with all feature modules physically absent.

No optional feature implementation or dependency may remain necessary for chassis startup.

### REQ-214 — Module removal acceptance is required

For every shipped feature module, disabling/removing it withdraws its capability while:

* the chassis remains usable;
* unrelated modules remain usable;
* retained data/provenance remains inspectable;
* retained settings remain available for restoration.

### REQ-215 — Offline wheel acceptance is end-to-end

Acceptance of executable-wheel delivery requires the real artifact, outside the checkout, with networking unavailable and no prepared cache.

A successful import or `--help` alone is insufficient.

The agent must complete meaningful module/workflow operations through separate nonterminal invocations.

### REQ-216 — Same-major compatibility is tested in both orders

For relevant releases, test:

```text
older -> newer -> older
newer -> older -> newer
```

against the same selected compatible state.

Verify settings, objects, revisions, provenance, assignments, and installed-surface integrity.

### REQ-217 — User-facing polish is acceptance-relevant

Primary CLI/TUI/web surfaces must remain understandable, contextual, and free of unnecessary clutter.

Adding every internal operation, identifier, diagnostic, or module command to the primary surface is not considered successful discoverability.

---

# 20. Remediation instructions

This section governs how the current conformance findings are used. It does not add product requirements beyond those above.

## 20.1 Use the conformance audit as the defect inventory

Use `chassis-design-conformance-2026-09-18.md` as the current implementation-remediation evidence.

Its findings identify known violations, risks, incomplete capabilities, and stale documentation.

Do not convert a finding's proposed implementation mechanism into a product requirement unless required by this document.

Do not create another independent requirement inventory from historical documents.

Create a remediation/compliance matrix whose requirement axis is **only the REQ IDs in this document** and whose defect axis contains the applicable audit findings.

## 20.2 Remediate outside-in

Begin from externally observable product boundaries because they expose hidden coupling without assuming the current internal architecture is correct.

Use this order unless an actual dependency requires moving a prerequisite earlier:

### Phase 1 — Prove the product boundary

Start with:

* empty `modules/`;
* all modules disabled;
* zero-module wheel;
* cold direct-wheel launch;
* module discovery from `modules/`;
* one single-file module;
* one package module;
* settings hydration;
* module removal;
* installed versus wheel state-root behavior.

Use the audit findings concerning packaged feature engines, special-cased dependencies, module paths, build paths, native packaging, and clean-wheel configuration as the starting defect set.

The first objective is to make it impossible for a test to succeed merely because excluded feature code remains hidden in the chassis or artifact.

### Phase 2 — Repair the extension boundary

With the external package boundary visible, repair:

* feature containment;
* public module-to-module operations;
* private cross-module imports;
* duplicated interface execution paths;
* sync/async universal data access;
* lifecycle rollback;
* concurrent unload;
* module reload ownership;
* escaped background work;
* developer template/API documentation.

Re-run the Phase 1 external journeys after each meaningful boundary repair.

### Phase 3 — Repair work identity and cooperation

Exercise from separate processes and transports:

* working-folder context;
* module context;
* nonce context;
* per-assignment workfolder;
* MCP interleaving;
* request/eventual-response;
* failure/cancellation responses;
* harness process ownership;
* host restart/reconciliation.

Trace failures inward rather than adding interface-specific exceptions.

### Phase 4 — Repair provenance and object integrity

Using the same public operations used by modules:

* capture exact consumed revisions;
* enforce inference provenance;
* provide one-reference provenance inspection;
* distinguish producing occurrence from equal content;
* verify dynamic context fetched after assignment issuance;
* verify historical reads after source mutation.

Do not repair these defects with interface-local logging.

### Phase 5 — Repair persistence, placement, and portable continuation

Exercise:

* split/unified relocation;
* interrupted import;
* interrupted payload writes;
* artifact-boundary exclusions;
* pending workfolder transfer;
* file/directory metadata;
* selected-origin export;
* migration of retained prior data.

Use external reconstruction and continuation as the test, not merely successful database reads.

### Phase 6 — Repair workflow and knowledge semantics

Then exercise:

* provider/property layer selection;
* unsupported selector behavior;
* shared-input regeneration;
* completion events;
* workflow grammar/bindings;
* lexicalization;
* edited replay;
* memory CRUD/search;
* Native variants;
* Latent attachment;
* Canonical Intake target forms.

These features should now be using the repaired module, execution, object, provenance, and portability boundaries rather than compensating for them.

### Phase 7 — Polish and simplify the exposed surfaces

After the mechanics share one path:

* remove duplicated or obsolete user-facing routes;
* make module ownership visible without flattening every command;
* make status complete;
* improve contextual help;
* keep advanced information discoverable but out of the default surface;
* correct stale developer guidance;
* remove documentation that presents obsolete module contracts as current.

Do not hide a remaining architectural defect merely to make the UI appear cleaner.

## 20.3 Keep the matrix live

For each audit finding record:

* applicable REQ IDs;
* confirmed violation or cleared risk;
* root cause;
* affected code/modules/artifacts;
* remediation item;
* verification journey;
* evidence;
* final disposition.

A finding is closed only when the corresponding external behavior and architectural boundary have been verified.

New implementation defects discovered during remediation are added to the defect side of this matrix.

They do not create new product requirements unless the user changes this specification.

## 20.4 Do not use requirement uncertainty as a general stop condition

If this specification already states the required observable behavior, choose an implementation compatible with it and proceed.

Record implementation decisions separately.

Escalate only when the implementation would otherwise have to invent semantic meaning, destroy or reinterpret retained data irreversibly, or violate two requirements that cannot simultaneously be satisfied.

## 20.5 Completion

Remediation is complete when:

* every confirmed audit violation is resolved or explicitly shown not to violate this specification;
* every incomplete capability required by this specification is implemented;
* the chassis operates with zero feature modules;
* every feature is actually module-contained;
* public operations are the authoritative cooperation path;
* exact provenance is retained across all reasoning paths;
* the polished contextual CLI can complete required workflows without web/MCP;
* the actual uploaded wheel can complete supported work offline without permanent installation;
* same-major wheel/installed operation preserves compatible shared state in both version orders;
* and the resulting user-facing surfaces remain contextual, understandable, and free of unnecessary clutter.
