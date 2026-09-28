# Metaform chassis: design-conformance audit

Date: 2026-09-18  
Status: review of the working tree; findings remain open; implementation halted

## Finding

**The current implementation does not satisfy the required chassis/module boundary.** Several removable module folders are command wrappers around feature engines implemented in the chassis. Other features cooperate through private imports or raw storage, bypassing the common execution and provenance surface. Selecting no modules for a wheel still packages optional feature implementations.

The universal namespace store, exact join references, contextual execution, event delivery, settings, and assignment mechanisms provide useful foundations. Their presence does not establish that every route uses them correctly. The principal repair is to make the public contracts complete and authoritative, then put each feature's implementation, resources, and dependency ownership inside its module.

This audit records the requirement, evidence, consequence, minimum correction, and proof needed. A proposed correction here has **not** been implemented. Missing product capabilities and unresolved decisions are identified separately from reproduced defects. Web presentation remains deferred; its backend boundary is included.

## 1. Controlling design and why it matters

The latest clarification is that features are implemented in modules; the chassis supplies object-driven cooperation, enforces provenance for inference, and provides common synchronous/asynchronous execution, data access, and an event data bus. Each module is one Python file or a self-contained folder under `modules/`. Built-in modules use the same contract as community modules.

The reason for that division is functional. A workflow inserts a namespace object and selected contributions into an actual prompt. An agent consumes that context and produces an answer. Another module may then use the answer as input. Throughout this sequence, the object's identity, exact consumed revisions, assignment, and producing relationship must survive. A module cannot substitute its own untracked execution path without making the resulting knowledge unreliable to inspect, select, hide, or reuse.

The chassis therefore owns the shared machinery that preserves those relationships. The feature module determines what an operation does. Storage placement is independent of that meaning: moving a join between databases must preserve its identity and its relationships. Removing a feature withdraws its executable contributions while retaining its stored objects, provenance, and settings for inspection or later reactivation.

### Responsibility boundary used by this review

| Chassis responsibility | Module responsibility |
| --- | --- |
| Discovery, activation, deactivation, compatibility, contribution ownership | Feature implementation and its owned assets/dependencies |
| Settings persistence, defaults/glue, common configuration menu | Python-declared settings, help, defaults, and generated feature configuration |
| Contextual CLI framework, status, administration, dispatch | Feature commands, parameters, help, availability predicates |
| Object/reference access, project ownership, storage placement and generic provenance | Domain join types and operations over them |
| Common sync/async execution, work identity, jobs, process registration | Harness adapters, workflow control, inference procedures, knowledge behavior |
| Object-referenced events and attributable subscriber execution | Topics, subscriptions, requests, responses and feature cooperation |
| Generic installed/portable entrypoint support | Building distributions and feature-specific transfer/restoration behavior |

Chassis administration is a chassis capability. The requirement does not remove its settings, module management, or common object-inspection commands. Similarly, helper files inside a module do not individually need a `from metaform import ...` statement. The test is ownership and dependency direction, not the number of such imports.

### Sources and precedence

The review follows explicit user corrections first, then current authored specifications, historical context, plans, and implementation evidence. This order is also recorded in [SOURCES.md](product/SOURCES.md). Key sources are:

- [Plugin-system responsibilities](plugin-system.md), especially R02–R05, R19–R21 and section 3.
- [Consolidated product requirements](product/PRODUCT-SPECIFICATION.md): CH, OBJ, DATA, AG, UX, WF, KG, INT, DIST and DEMO identifiers.
- [Namespace and join clarification](namespace-join-implementation-plan.md): the universal envelope, owned open joins, persistent IDs, exact references, mirrors and configurable placement.
- [Current Canonical Intake](Canonical_Intake.xml), for the authored intake procedure and encounter-specific EF representation.
- [Global data pattern](global-data.md) and [data-folder account](data_folder.md).
- The latest conversation requirements: `modules/`, file/folder containment, module-to-command menu, construction documentation, executable-wheel configuration generated from module code, and object-driven public interaction with enforced inference provenance.

Conflicts among these documents are recorded in section 8. They are not silently resolved by changing authored prompts or protected instruction files.

## 2. Reviewed state and audit method

| Item | State |
| --- | --- |
| Repository | `/home/rich/metaform` |
| Branch | `realignment-2026-09-10` |
| HEAD | `ff6d53f5533d071612ceb574a94338efdffa3af9` |
| Review target | Actual dirty/untracked working tree, not HEAD alone |
| Freeze capture | `2026-09-18T14:25:58.996451+00:00` |
| Capture | [scan-state.json](../artifacts/design-conformance-2026-09-18/scan-state.json): Git state and hashes for 967 files |
| Scope | Active chassis entrypoints, public services, discovery/lifecycle, all 11 module folders, intermodule paths, universal data/provenance, workflows/intake/layers, harness/MCP, distribution, documentation and existing verification evidence |

Independent read-only reviews covered module layout/lifecycle, packaging/import closure, universal data/provenance, workflow/knowledge behavior, assignments/events/harnesses, and requirement coverage. The root review also traced the web adapter's cross-module imports and write path. Synthetic diagnostics use in-memory state. Findings explicitly marked static have not been fault-injected or reproduced in a running installation.

The root independently reproduced the in-memory diagnostics and inspected the zero-module wheel. [verification.json](../artifacts/design-conformance-2026-09-18/verification.json) retains the probe commands/results, wheel contents and dependency metadata, and the final baseline/link checks. All 967 baseline files remained byte-identical through the audit; the audit report and evidence are new files.

### Partial changes already present when development stopped

The source examples had been moved from `examples/plugins/` to top-level `modules/`. All 94 original files were checked unchanged during that move. Source-path/documentation references were updated in 47 active files, and `modules/README.md` was added. Runtime discovery and installed paths still use `plugins/`; this was an incomplete transition.

A stricter `tests/test_distribution_boundary.py` had also been added. Its first run failed because a wheel built with zero modules contained `metaform/artifact_history.py`. It failed before launching a recipient runtime. The existing Claude launch fix was already present. No feature extraction was performed by the agents assigned workflow or MCP extraction before they were stopped.

These changes are part of the reviewed state, not repairs made during this audit. Source files, prompts, dependencies, protected instructions, and user data are preserved during the freeze.

## 3. Modularity and public-service findings

### M01 — High: optional feature engines are implemented in the chassis

**Requirement:** CH-01/03/04; plugin-system section 3; latest feature ownership and containment instructions.

| Module folder | Feature implementation outside that folder |
| --- | --- |
| `modules/knowledge` | `src/metaform/namespace_layers.py` |
| `modules/history` | `src/metaform/artifact_history.py` |
| `modules/workflows` | `src/metaform/intake_documents.py`, `src/metaform/system_workflows.py`, maintained intake/latent resources and workflow grammar under `src/metaform/data/` |
| `modules/mcp` | `src/metaform/chassis_mcp.py` |
| `modules/distribution` | `src/metaform/distribution.py`, `src/metaform/distribution_closure.py` |

For example, `modules/history/__init__.py:7` imports `ArtifactHistory`; the snapshot, variant, reconstruction and import policy is in core. `modules/knowledge/__init__.py:7` imports `Layers`, while `modules/workflows/engine.py:91` uses the same core implementation directly. Disabling knowledge removes its commands but leaves its behavior available through workflows.

**Why it matters:** copying or removing the apparent module does not copy or remove the feature. The chassis must change whenever those features change. An independent module author cannot reproduce the same arrangement through the advertised public contract.

**Minimum correction:** contain complete feature implementations and resources with their modules. Keep universal object access, execution context and provenance in core. Keep intake as a maintained workflow within the workflow feature; this finding does not call for a separate intake module.

**Required proof:** remove each owning module, inspect package/import closure, and verify that core administration plus an unrelated module work. Plain workflows must be usable without optional knowledge behavior; a workflow that explicitly requests unavailable knowledge needs an accurate availability result.

### M02 — High: a zero-module wheel still ships optional and earlier implementations

**Evidence:** `src/metaform/distribution.py:206` copies the whole `metaform` package; `pyproject.toml:38` likewise packages the entire source tree. The boundary test's observed failure is `metaform/artifact_history.py` appearing after `build(root, [])`.

The copied tree also includes earlier App, intake, graph and module implementations, manifests, templates, and assets. The public `src/metaform/modules/__init__.py` catalog facade sits beside older feature files in that package. Their physical presence is established; this does not mean the fresh namespace store itself uses the older EF representation.

**Why it matters:** module selection changes external wrappers without establishing a minimal delivered chassis. A clean-room test can accidentally succeed because excluded engines remain inside the wheel.

**Minimum correction:** package a defined chassis boundary plus selected complete modules and their declared requirements. Preserve earlier work outside the active package boundary rather than deleting it as part of this review.

**Required proof:** inspect contents and import closure of both a zero-module wheel and a one-module wheel, then execute each with no checkout, site-packages or network fallback.

### M03 — High: dependency selection gives built-in names special treatment

**Evidence:** `pyproject.toml:14` makes MCP, Flask, Jinja2, build/hatchling and other feature-related packages unconditional. `src/metaform/packaging.py:126` unconditionally bundles Flask/Jinja/Werkzeug. `distribution.py:209` copies the original metadata; `distribution.py:242` adds packages based on the literal module IDs `web`, `terminal`, and `mcp`.

**Why it matters:** an independent module or renamed equivalent cannot declare its needs through the same path. A core-only installation inherits optional dependencies and their platform constraints.

**Minimum correction:** derive feature requirements from module-owned declarations, retain only actual chassis requirements in the base package, and generate matching distribution metadata. The exact declaration format is an interface choice still to make.

**Required proof:** an independently named module with an additional dependency builds and runs offline; excluded module dependencies are absent from both archive contents and `Requires-Dist`.

### M04 — High: existing cooperation depends on private implementation access

**Evidence:** `src/metaform/modules/__init__.py` exposes catalog/describe and async counterparts, but no public cross-module invocation. `cli.invoke/ainvoke` and `work.submit_job/asubmit_job` target only the current module. Feature code therefore accesses `current().runtime`, concrete stores, or other feature engines directly. Examples include workflow control and execution, distribution/history coupling, and the web path in M05. The harness launch string hardcodes `python -m metaform.chassis_mcp` in `modules/harness_runner/mcp_launch.py:14`.

Events already provide real cooperation. The gap is the incomplete public contract for the direct cooperation already used by shipped features, including contributed transfer/restore behavior and transport launch resolution.

**Why it matters:** these modules depend on implementation details rather than a stable object/context contract. Lifecycle, visibility, provenance and availability can differ by caller.

**Minimum correction:** expose needed cooperation through the chassis's documented operation/event services, retaining object references and active work context. Feature-specific transfer and transport behavior must be supplied by its owner. Do not treat earlier proposed hook names as an already implemented API.

**Required proof:** a separately authored caller invokes another module without importing its implementation, receives immediate or deferred results, and retains causal provenance. Removing the provider produces a clear availability result and leaves unrelated work functional.

### M05 — High: the web adapter creates a second workflow execution path

**Evidence:** `modules/web/workflow_ui.py:27` finds the literal `workflows` module and imports its private `.engine`. It caches that import by source path. At `:121` it constructs `WorkflowEngine` over raw `store.namespace_store(project)` and directly calls save, source, issue and answer methods. `modules/web/__init__.py:240` mounts these routes directly, alongside the generic contribution mechanism.

The engine does retain `workflow.provenance` joins for answers. However, these calls bypass `Runtime.invoke/_execute`, do not establish a common execution producer, and do not use the same tracked operation path as CLI work. The independent import cache also has no activation-based refresh corresponding to the contribution registry.

**Why it matters:** the interface knows the feature's implementation layout and duplicates its activation/dispatch assumptions. Inference provenance becomes dependent on which interface wrote the answer. Reloaded module state can diverge from the cached engine.

**Minimum correction:** route feature operations through the common public execution surface; use the extensible contribution mechanism for workflow-owned integration. Keep transport rendering in the web module and workflow behavior in its owner.

**Required proof:** the same object operation through CLI and web returns the same class of provenance/context evidence. Disable, remove and reactivate workflows without stale handlers. This is a backend test, not a web redesign.

### M06 — Medium: universal namespace access lacks a shared asynchronous surface

**Evidence:** `data/__init__.py:51` provides async helpers for compatibility `Record` operations. `namespace_service.py:10` and `:52` expose synchronous namespace methods, including locks and SQLite work. An async module working with the actual universal joins must arrange its own thread boundary.

**Why it matters:** the central object API is less complete than the example record API. Module authors are pushed into blocking shared execution or duplicating context-sensitive dispatch code.

**Minimum correction:** provide documented sync and async access to the same universal namespace operations, preserving the active producer and project.

**Required proof:** an async module reads and writes owned joins through public services while a second operation stays responsive; both outputs have the correct context and consumed revisions.

### M07 — Medium: the installed directory contract still says `plugins/`

**Evidence:** `plugin_runtime.py:25,250`, `module_catalog.py:10`, `plugin_policy.py:11`, `tui.py:171`, distribution seed/bootstrap, and web/terminal subprocess paths use `<root>/plugins`. Source modules are now at repository `modules/`.

**Why it matters:** copying a module to the requested runtime `modules/` directory does not discover it. The disabled file, setup guidance and installed layout disagree with the user's contract.

**Minimum correction:** apply the canonical `modules/` and `modules/disabled` paths consistently, with explicit preservation of any existing installed state.

**Required proof:** single-file and folder modules are discovered, disabled, removed, restored, packaged and launched using that directory alone. Current tests that create `root/plugins` do not prove this.

### M08 — Medium: the base menu loses command ownership

**Evidence:** `contextual_cli.py:92` flattens contributed commands. At `:163`, “Module menus” shows an entry and description but not the commands owned by each module. JSON help at `:135` provides separate flat command/module lists.

**Why it matters:** users cannot inspect the module boundary through the interface. The requested loaded-module-to-command menu is absent even though the registry has enough information.

**Minimum correction:** render ownership from the same resolved registry and availability context used for dispatch.

**Required proof:** the menu shows each loaded module's currently available commands; a setting, nonce, disable or removal updates both dispatch and its owning menu section.

### M09 — Medium: most shipped modules lack OS declarations

**Evidence:** only `modules/terminal/__init__.py:2` declares `SUPPORTED_OS`; the other ten entrypoints omit it. `module_metadata.py:62` permits undeclared modules and reports their support as undeclared.

**Why it matters:** platform-dependent features are supposed to carry their compatibility policy so the Python chassis stays usable across systems. Most shipped modules do not supply that account.

**Minimum correction:** supply accurate declarations with each module. Declared compatibility and platforms actually exercised must remain distinguishable.

**Required proof:** an unsupported module is identified before import while the chassis and compatible modules load. Native Windows and macOS remain unverified; simulated OS metadata checks do not establish them.

### M10 — Medium: the templates and module guides do not cover the current contract

All 11 modules have READMEs. Only `showcase`, `event_requester`, and `harness_runner` explain construction from the common template. Distribution, history, knowledge, MCP, record_demo, terminal, web and workflows lack that construction account.

The showcase demonstrates `data.put` and compatibility record provenance at `modules/showcase/__init__.py:33`. It does not demonstrate a `NamespaceObject`, receiver-owned typed joins, `data.namespace_store()`, or exact `JoinRef` access. Its “all-services” feature map consequently omits the central current object model.

**Why it matters:** a community developer following the template will learn the narrower earlier facade while the real features depend on undocumented internals.

**Minimum correction:** make the standalone template demonstrate the universal object/provenance contract and explain each shipped module's settings, commands, events, work, resources and teardown as a derivation from it.

**Required proof:** follow those guides from a clean chassis to construct an independent module, an event request/response pair, and a wheel with generated configuration.

### M11 — High: build entrypoints do not share one portable contract

**Evidence:** `tools/build_distribution.py:9` still imports the earlier `App`, `packaging.build`, and old service shutdown. The current distribution module uses a different builder. `packaging/__main__.py` does not call `portable_runtime.activate()`, whereas the entrypoint generated at `distribution.py:37` does. Standard Hatch packaging has no equivalent dependency-bundling declaration.

Normal CLI startup also imports `distribution.bootstrap` at `contextual_cli.py:705`; bootstrap imports the earlier `history.safe_path` before deciding whether a seed exists. Distribution uses older `packaging`, `portable`, and `workfolders` files for generic helpers, carrying wider implementation dependencies along with them.

**Why it matters:** “the wheel works” describes one custom build route, not every documented release path. Core startup is coupled to the distribution feature and older helpers.

**Minimum correction:** isolate generic portable startup from distribution building and route supported builds through one current contract. Preserve useful helper behavior while removing its dependency on earlier feature implementations.

**Required proof:** build through the documented release command, run that exact wheel with `python -S`, no checkout or network, and re-export it with selected modules.

### M12 — Medium: module-contained native assets are not included in wheel tagging

**Evidence:** `distribution.py:217` copies selected folders wholesale. Native detection at `:129` examines copied installed dependency distributions, not the selected module folders; `:258` derives the wheel tag from that scan.

**Why it matters:** a module with a native extension can be distributed in an artifact marked `py3-none-any` despite its platform dependence.

**Minimum correction:** account for native module assets in compatibility determination, consistently with module OS declarations.

**Required proof:** a module containing a native asset receives an accurate wheel compatibility tag and cannot silently claim portability on an unsupported interpreter/platform.

### M13 — High, static rollback defect: failed activation can leave a broken live module

`plugin_runtime.py:214` persists registration, then `:215` publishes the module in `self.plugins`, before installing declared subscriptions. If a subscription entry raises at `:218`, cleanup removes definitions, ownership bookkeeping and private imports but leaves `self.plugins` populated. Discovery at `:299` subsequently skips that ID as already loaded.

**Why it matters:** one failed module can leave commands visible with their backing ownership state removed. Administration can report a usable feature that cannot be invoked or unloaded consistently.

**Minimum correction and proof:** publish completed registrations atomically or withdraw every published contribution on failure. Exercise a failure after publication, then inspect menus, subscriptions, reload and unrelated modules. Preserve saved settings and failed-operation evidence. The existing failing-start test stops before this failure window.

### M14 — Medium, static concurrency defect: concurrent unload does not await common teardown

`plugin_runtime.py:674` removes the live module before teardown. A second caller sees it missing at `:675` and returns while the first caller may still be waiting for jobs, callbacks or `stop()`.

**Why it matters:** the shared runtime can acknowledge completed removal while owned resources are still active. A replacement or dependent operation can race that teardown.

**Minimum correction and proof:** retain one in-progress teardown result and have all unload callers await it. Two concurrent clients must receive completion only after the same owned resources settle.

### M15 — Medium: bare sibling imports escape per-module reload ownership

`plugin_runtime.py:23` adds the shared module directory to process-wide `sys.path`. Per-module cleanup removes its private `_metaform_live_*` package, while bare helper imports can remain cached until the whole directory lease closes at `:37`.

**Why it matters:** a changed bare helper can remain stale after consumer reload. Two embedded runtimes with different roots can also share the first module cached under a bare name. Relative imports within self-contained packages already have private identities and avoid this case.

**Minimum correction and proof:** keep implementation helpers within their module package and use shared services for feature cooperation. Define lifetime explicitly if ordinary cross-package dependencies remain supported. Verify reload after changing a helper and concurrent roots with identically named helpers.

### M16 — Medium, contract limit: unregistered child tasks retain stale producing context

The runtime tracks its own operation, job and delivery tasks at `plugin_runtime.py:340,419,645`. A callback can create an independent `asyncio.create_task()` child which inherits context but is not registered in these collections. Public data writes check that a producer exists, not whether it has already completed or its module has unloaded.

**Why it matters:** an escaped child can outlive its parent and write under a completed producer. Claims that all async work is settled and independently attributable exceed the current supported service boundary.

**Minimum correction and proof:** make the supported background-work ownership contract explicit and enforce producing-context lifecycle at that boundary. Exercise a child attempting to outlive its parent/unload. This is not a proposal to sandbox arbitrary Python; supplied modules should use chassis-owned background services.

## 4. Object, provenance and data findings

### P01 — High: exact consumed context is lost on two public paths

**Evidence:** `ContextualNamespaces.get/list` at `namespace_service.py:76` return full join content but record only a revisionless `NamespaceRef`. `chassis_mcp.py:127` obtains nonce context, then performs namespace/resolve reads on raw storage without recording those inputs. An in-memory probe confirmed the namespace-read behavior.

**Why it matters:** an output may trace to an object name but not to the actual object content the model read. A later edit makes the apparent explanation of the inference different from its real inputs. Initial assignment bindings being pinned does not repair additional context fetched through MCP.

**Minimum correction:** distinguish identity lookup from content delivery. Every tracked content read must retain the exact served join revisions through the common data service.

**Required proof:** consume additional context through both public namespace reads and MCP, produce an inference, change the source, and inspect the output to recover the original consumed revisions.

### P02 — High: inference provenance is optional evidence, not an enforced common contract

**Evidence:** `Runtime.invoke` at `plugin_runtime.py:382` accepts optional provenance. `Store.begin_producer` at `plugin_store.py:182` defaults evidence to an empty object. `data.put` requires a producer, but `ContextualNamespaces.put_join` at `namespace_service.py:96` allows an unbound write. `contextual_cli.bind_command` at `:175` binds a module/project context without a producer, so a contributed Click callback can take that public write path directly. Thus having an operation ID does not establish the prompt revision, rendered prompt, binding map and exact inference inputs; some public paths do not even establish the operation.

**Why it matters:** a generic “operation happened” record cannot answer why an inference says what it says. Feature authors and interface adapters can omit the context the system promises to preserve.

**Minimum correction:** provide an explicit common inference execution/recording contract that carries the issued prompt, bindings, exact inputs, answer and output occurrence. Authoring and importing still need their actual provenance without inventing an inference. Arbitrary join type strings must remain open; this correction does not authorize guessing from those strings or judging answer content.

**Required proof:** an independent inference module uses the public contract and cannot report successful inference recording with its producing context omitted. CLI, event, job and transport paths retain the same evidence.

### P03 — High: there is no universal one-reference provenance inspection

**Evidence:** `data.provenance` at `data/__init__.py:43` reads the compatibility Record surface; `production_joins.record` at `:193` filters to `service == 'metaform.data'`. `data.resolve` returns the join only. `producer_value` at `production_joins.py:90` also omits automatically observed `dependencies` and `outputs` from its public projection. Workflow inspect similarly returns one raw join.

**Why it matters:** storage contains useful mirrors, but every consumer must reconstruct a different traversal to explain an arbitrary output. The requested click-through from output to actual prompt, inserted data and previous producing steps lacks a common read surface.

**Minimum correction:** expose reference-based provenance inspection over universal joins and retained producer evidence, including inputs observed during execution rather than only arguments.

**Required proof:** the same inspection API explains a custom module output, workflow answer, imported history and dynamically read input. Following step three's inserted step-two output must lead to step two's actual prompt and inputs.

### P04 — High: independent producing occurrences can collapse to one output reference

**Evidence:** unchanged joins deduplicate at `namespace_store.py:180`; each operation can add a different provenance mirror at `production_joins.py:96`. `test_namespace_production.py:71` expects the same output reference with two mirrors. Visibility at `namespace_layers.py:177` traverses every mirror for that output.

**Observed:** an in-memory diagnostic constructed the two-mirror state, one using source A and one using source B, for one exact output. Hiding only A hid that output even though B remained visible. The production path's ability to create this state is separately established by the existing test that expects the same output reference and two producing mirrors.

**Why it matters:** equal content is not equal causation. The identity cannot distinguish which generation was selected, and dependency hiding combines histories that should remain independently inspectable.

**Minimum correction:** distinguish a producing occurrence from content deduplication while preserving idempotent import and copied join identities.

**Required proof:** independent generations with identical content remain separately traceable/selectable; hiding A affects A's derivation without erasing B's independent result.

### P05 — Medium: changing split/unified routes can leave joins in the wrong database

**Evidence:** `namespace_service.configure` at `:155` imports existing exports into the target layout. `namespace_store.py:259` skips a revision found anywhere among target databases, regardless of the requested destination.

**Observed:** unified main containing a provenance join was changed to split main/history, reusing the original main and routing provenance to history. The copy reported `imported: 0, unchanged: 1`; history contained zero joins.

**Why it matters:** logical resolution continues working, concealing that the user's requested physical organization was never applied. A later selected backup can omit the expected data.

**Minimum correction:** reconcile destination placement as well as identity/content, preserving source copies and reference identity.

**Required proof:** inspect the target database files after redistribution, then verify exact references and selective export.

### P06 — Medium: artifact capture includes active navigation and nonce markers

**Evidence:** `ArtifactHistory._snapshot` at `artifact_history.py:140` excludes `.git` and its own payload root, but captures `.agentid/nonce` and `.metaform-context`. DATA-11 excludes these ephemeral bindings.

**Why it matters:** entering a module or assignment becomes an artifact modification. Reconstructing the artifact can restore stale active-work bindings.

**Minimum correction:** apply the agreed artifact-boundary exclusions consistently in baseline and variant capture.

**Required proof:** entering/exiting work does not change an otherwise identical artifact snapshot, and reconstructed sources contain no active binding markers.

### P07 — High: portable continuation loses dedicated pending-workfolder files

**Evidence:** `distribution.py:225` captures the project's registered source folder when requested. It does not capture dedicated pending-step workfolders. `portable_assignments.py:109` creates new empty directories for non-root pending paths. The transfer test checks prompts, headers, answers and paths, but does not seed required files in a waiting dedicated folder.

**Why it matters:** the same nonce and prompt can resume against different physical inputs. Staged or already produced files may be lost, despite the continuation appearing intact.

**Minimum correction:** the owning feature must contribute capture/restoration of actual pending work, using generic portable storage services.

**Required proof:** transfer a waiting assignment with text, binary and agent-produced files, remove access to the sender, and continue with byte-identical restored inputs.

### P08 — Medium, static recovery gap: portable imports span uncoordinated commits and file writes

**Evidence:** `distribution.py:335` commits shared state before project state; `:343` imports project records before writing module/source files; `:370` records completion afterward. Multi-database relocation also lacks demonstrated interrupted-copy/retry recovery.

**Why it matters:** failure between phases can leave an installation partially applied. Individual idempotent imports do not establish recovery of the combined state.

**Minimum correction:** make import/relocation staged and recoverable across namespace data, payloads, files and completion state.

**Required proof:** inject a failure at each phase boundary and verify preserved prior data plus deterministic retry. No such fault injection was performed during this audit.

### P09 — Medium: portable source extraction drops directory modes

**Evidence:** `portable.py:112` captures directory modes. `distribution.py:350` recreates directories and continues without applying them; file modes are applied at `:363`.

**Why it matters:** exported metadata does not reproduce the source tree's access behavior, contrary to DATA-11 fidelity.

**Minimum correction:** restore supported directory metadata after populating the tree.

**Required proof:** transfer a source tree with an explicitly restricted directory and verify its restored mode, while stating platform differences accurately.

## 5. Knowledge and workflow behavior

### B01 — High, reproduced: property context bypasses layer selection

`namespace_layers.py:215` collects every non-control join from a property's provider. `modules/workflows/operations.py:197` inserts those references into the inference binding; `engine.py:104` checks selected attachment ownership only on the receiving object.

A memory attached to `code.cpp` in an unselected layer appeared in the `code.engine` inference prompt with `layer_select=False`. The diagnostic returned:

```text
optional_layer_selected = []
provider_advice_in_property_refs = True
provider_advice_in_prompt = True
```

**Why it matters:** a workflow intended to reason from intake-only context can receive excluded inference through a property. That changes the reasoning basis while the selector still appears correct.

**Minimum correction:** resolve the provider's relevant Type/property context and its selected knowledge through the same selection rules, retaining exact contributing references. Prove excluded provider knowledge stays out of the rendered prompt and recorded inputs.

### B02 — Medium: unsupported selectors silently become project defaults

`engine.py:100` maps an unrecognized dictionary with non-boolean values to `None`; `namespace_layers.py:99` interprets `None` as the project default, potentially selecting all layers.

**Why it matters:** preserving authored selector data in storage is insufficient if execution silently gives it a different meaning.

**Minimum correction and proof:** retain the original data and report unresolved executable selection instead of silently substituting the default. Test both preserved data and actual delivered context. This concerns instruction resolution, not semantic rejection of agent answers.

### B03 — Medium: accepted shared inputs cannot drive selective regeneration

`operations.py:207` accepts explicit `@metaform` inputs, but `regeneration.py:37` rejects all changed references outside the current project.

**Why it matters:** the system can produce project knowledge from shared context but cannot select the affected subjects when that shared context changes.

**Minimum correction and proof:** apply the same explicit own/shared scope contract to regeneration; update a consumed shared revision and verify only dependent subjects are selected.

### B04 — Medium, static path: tool completion can omit the completion event

`execution.py:239` advances a tool result and discards the returned run revision. At `:257`, the driver emits change events only when its local reference changes; an already terminal `advance` returns its input reference at `:108`.

**Why it matters:** a run can reach completion between driver iterations without publishing the final `workflow.completed` notification. Other modules or a live view can remain behind the stored state.

**Minimum correction and proof:** track observed state transitions across all completion paths and exercise a tool finishing between driver iterations. Verify attributable completion delivery and final stored state agree.

### B05 — Medium: workflow conversion grammar omits executable object bindings

`src/metaform/data/workflows/grammar.json:3` documents prompts/inputs but omits segments, project/namespace bindings, exact contribution references and layer selectors. `modules/workflows/preparation.py:15` asks the agent to preserve object references using that grammar.

**Why it matters:** the agent is asked to infer an executable object procedure without being given the binding shape that makes it object-driven.

**Minimum correction and proof:** document the implemented object shape in the module-owned grammar; exercise an actual imported procedure containing references, preserve its authored source, and inspect the generated bindings and prompt.

### B06 — Medium: human-readable status omits assignment delivery fields

The human-readable branch at `contextual_cli.py:255` shows assignment prompt/step but omits the header and knowledge addresses supplied by contextual help and JSON status.

**Why it matters:** the explicit status command does not fully deliver the information UX-07 says an agent should receive there.

**Minimum correction and proof:** show the existing header and knowledge addresses in human-readable status; compare it with the same assignment's JSON/help delivery.

### B07 — High: shared MCP uses the server's folder for every assignment

`chassis_mcp.py:55` fixes `working_dir` at server construction; `_work` at `:69` combines that folder with each nonce's separately resolved project/module. `assignments.py:23` does not persist an assignment workfolder, and `begin` at `:129` writes the local marker without retaining that location. Completion cleanup at `:200` searches only the supplied folder.

**Why it matters:** one shared transport can use the correct nonce but the wrong working folder for a second assignment. It can also leave that assignment's actual marker behind. A separately launched server happens to work when its cwd matches the one assignment.

**Minimum correction and proof:** resolve persistent assignment folder context per nonce. Serve two assignments in different folders from one server, verify each operation's context, and independently complete/clean both.

### B08 — Medium: failed and cancelled harness work has no response event

`modules/harness_runner/__init__.py:106` raises on nonzero exit before publishing `harness.response`. Cancellation/error branches at `:117` retain records but publish no terminal response. The requester at `modules/event_requester/__init__.py:17` subscribes only to that response topic.

**Why it matters:** the demonstrated nonblocking request/response contract disappears on failure or cancellation. Polling the jobs table can expose the outcome, but the cooperating module is not notified.

**Minimum correction and proof:** deliver the retained terminal outcome reference for success, failure and cancellation through the same response contract. Verify each outcome reaches the requester once with its causal context, while the initial request returns before agent completion.

### B09 — Medium: Windows harness cancellation does not own provider descendants

`modules/harness_runner/__init__.py:23` terminates a POSIX process group but only the immediate adapter process elsewhere. `adapter.py:50` starts the real provider as a child. Existing descendant cleanup coverage is POSIX-only, and the module declares no OS limitation.

**Why it matters:** on Windows, cancelling the module's work can leave the actual provider or MCP descendant running. This contradicts treating the feature as portable and fully settled on removal.

**Minimum correction and proof:** supply module-owned process-tree management for the platform, or accurately declare support until it exists. On every declared platform, cancellation must stop the adapter, provider and owned transport descendants.

### B10 — Medium, recovery gap: host restart does not reconcile detached harness processes

`plugin_store.py:377` marks jobs interrupted after host death; `plugin_runtime.py:529` cancels only in-memory jobs. Detached harness processes can outlive a killed host, and recovery has no demonstrated process reconciliation. Existing crash coverage uses sleeping coroutine work.

**Why it matters:** recorded job state and actual owned processes can disagree after a restart. This is a work-ownership issue, not a requirement for automatic replay.

**Minimum correction and proof:** reconcile retained process identity with interrupted work after host restart. Kill an isolated host with an actual owned child running, restart it, and verify accurate status and controlled cleanup without affecting unrelated processes.

## 6. Agreed capabilities still incomplete

These are outstanding product deliveries. They do not justify discarding the universal storage shape or rewriting requirements to fit current behavior.

| ID | Requirement and present gap | Evidence | Required demonstration |
| --- | --- | --- | --- |
| C01 | WF-03: explicit agent lexicalization of an existing procedure into project object references | `modules/workflows/__init__.py:169` has no lexicalization operation; import preparation preserves supplied bindings but is a different task | Retain an imported procedure, lexicalize its nouns, preserve the original revision, and inspect project-bound prompt text |
| C02 | WF-06: replay from an edited step while reusing prior outputs | `execution.py:51` starts new runs with empty outputs; resume retains the original pinned definition | Complete A, revise B, reuse A and issue revised B plus descendants; keep original run history |
| C03 | WF-04: step selector and separate imperative-footer/object-index assembly | `engine.py:151`, `control.py:150` use workflow/binding selectors; no step selector path | Show selected step context, appended imperatives and object index; settle unresolved step/workflow precedence explicitly |
| C04 | KG-08: memory search, update and individual deletion | `modules/knowledge/__init__.py:113` exposes remember/view; raw memory revision does not retarget a pinned attachment | Update one memory, inspect its history, find it, remove it from active selection without hiding its whole namespace object |
| C05 | DATA-09: Native interpretation variants and applicability-sensitive regeneration | `IMPLEMENTATION-PLAN.md:314`; `regeneration.py:49` selects only previously consumed identities | Preserve the original interpretation; introduce a newly relevant property absent from prior inputs and select its affected subjects |
| C06 | INT-07: Latent findings attached as separately attributed knowledge at relevant objects/joins | `system_workflows.py:63` produces a retained output; the complete attachment journey is absent | Native account → independent Latent reasoning → attributable browsable knowledge on its subjects, preserving arbitrary answers |
| C07 | INT-05: maintained intake for URL, Type and inline Content targets | `operations.py:109` currently requires an existing local path | Use the authored Canonical procedure through the same workflow path for each supported target form |
| C08 | UX-09: dynamic onboarding, workflow catalog and unfamiliar-harness provisioning | `contextual_cli.py:204` makes `skill` an alias of ordinary help; provisioning remains an explicit design question | A new installation explains available modules/workflows and guides the supported harness setup |
| C09 | DATA-10: preserving earlier stored data through explicit conversion/reference mapping | `IMPLEMENTATION-PLAN.md:202` leaves migration open; compatibility reads still fall back to earlier tables | Preserve a copy, convert known prior data, retain source and reference mapping, and inspect unresolved cases |
| C10 | Global-data selected-origin export/resume | `modules/history/__init__.py:57` exports the project namespace; no selected-origin export argument | Export one retained origin and the necessary lineage without unrelated origins |
| C11 | DATA-03: actual authoring/import provenance on unassigned CLI writes | `contextual_cli.py:577` creates a producer only for nonce-bound put-join | An authored join records its real authoring operation/source without inventing an agent prompt |
| C12 | Module-owned configuration generation from a clean direct wheel | Python settings/defaults exist; web writes runtime config and the harness creates launch config, but the combined journey is untested | No checkout access, read-only wheel location, writable user data root; generate config, change settings, reset with glue, recreate config |
| C13 | Semantic acceptance of Native/Latent and actual imported-workflow conversion, followed by verification after boundary repairs | Real Codex code/document Native and Latent runs completed; a subtype-interpretation issue remains flagged. Claude's longer Native attempt timed out. Preservation fixtures do not establish agent conversion quality | Review actual retained outputs against the authored procedure; verify the repaired paths with substantive provider runs and actual conversion outputs |

Project source-change reporting (UX-10), stale-versus-hidden inference behavior, and interrupted storage recovery also remain unproven as complete journeys. Existing component behavior must not be described as completion of those requirements.

## 7. Public contract inventory

| Public surface | Implemented mechanism | Material gap in this audit |
| --- | --- | --- |
| `settings` | Python `Setting` declarations; persisted values; defaults; glue; sync/async access | Per-module teaching and clean-wheel generated-config proof |
| `cli` | Click contributions; contextual help; own-module `invoke/ainvoke`; immutable command context | Module-to-command menu; public cross-module calls; status delivery parity |
| `event` | Sync/async publish, dynamic subscribe/unsubscribe, typed reference transport, attributable deliveries and history | All feature paths must use it consistently; B04 identifies a missing workflow transition notification |
| `data` | Compatibility record sync/async methods; universal namespace/owned-join store; exact references | Universal async methods, exact read capture, universal provenance inspection and enforced inference context |
| `work` | Assignment/header, background jobs, sync/async entrypoints, process registration, completion | Per-nonce workfolder context, process recovery, and feature-independent launch contract |
| `modules` | Catalog/describe with sync/async counterparts | Complete documented cooperation/dependency contract for currently private feature interactions |
| `Plugin` | Operations, Click commands, settings, subscriptions, lifecycle, conditional availability, help, API version | Owned dependency/transfer requirements are not expressed by the current declaration; direct features compensate in private code |

The event bus's object references can address stored messages, answers and variables. There is no need to invent a second mutable global variable store to satisfy the exchange requirement. The audit concerns whether every actual path preserves the shared object and producing context.

## 8. Specification and documentation conflicts

### D01 — High: the implementation plan codifies the wrong feature boundary

`IMPLEMENTATION-PLAN.md:269` places `Layers` in core, `:312` places `ArtifactHistory` there, and `:363` places distribution building there. History and knowledge guides call those engines chassis services. This conflicts with CH-01/03, plugin-system section 3 and the latest explicit requirement.

**Why it matters:** another implementation following this plan would reproduce the current violation. The plan needs correction when remediation begins; folder moves alone cannot resolve it.

### D02 — High: the consolidated specification still contains superseded object semantics

`product/PRODUCT-SPECIFICATION.md:68` describes a single EF at Type resolution; `:128` leaves the universal envelope unresolved. The current Canonical and later namespace explanation establish encounter-specific EF in RE-owned joins and the exact `namespace_address`, `name_length`, `joins` envelope. `specifications/README.md:18` still prioritizes old `intake.xml` and `re.schema.json`, whose shape requires element-level EF and aliases.

The declarative `product/UNDERSTANDING.md` also repeats the older single-EF account. Its discussion of the purpose of prepared project understanding remains relevant, but its older representation wording is not authority over current Canonical Intake.

**Why it matters:** a purported single source of truth currently directs developers to incompatible shapes. Reconciliation must identify superseded claims without modifying user-authored prompts to match runtime conveniences.

### D03 — Medium: current Canonical and historical copies need explicit authority

The current `specifications/Canonical_Intake.xml` and maintained packaged copy match byte-for-byte:

```text
cf7631829193bebfed3fdd052888cca14f2f4d5ad87680ec86295779bee5c614
```

`specifications/xml/Canonical_Intake.xml` differs. The current Canonical also retains `media`, while the conversation and decision ledger specify `asset`; the conversation additionally introduces an `entity` trunk. Its method names `TARGET`, while the final schema names `purpose`; some prose names `re`/`pe` while nesting supplies the receiver in the final form.

These are authored-source discrepancies to resolve explicitly. They do not authorize the audit to edit the Canonical, manufacture a new glossary, or silently impose intake vocabulary on unrelated joins.

### D04 — Medium: two incompatible developer module contracts are presented

`examples/module/README.md:7` teaches the earlier `ModuleAPI`; `:40` requires `module.json`. Current modules use Python `PLUGIN`, shared services, Click commands and code-owned settings. The earlier example is not prominently historical.

The root README, public API guide, product specification and TUI also continue to prescribe runtime `plugins/`. The latest user requirement is `modules/`.

**Why it matters:** community authors can follow apparently current documentation into an unsupported extension model.

### D05 — Medium: broken source links and protected stale guidance

The main specification index links deleted `specs/data_folder.md`. `product/SOURCES.md:46` still links removed `examples/plugins` guides and old `specs/sample`/`specs/xml` paths. The protected `.agents/skills/metaform-dev/SKILL.md` describes the earlier argparse/manifest runtime and earlier source files.

These instruction files were preserved. Their stale map is recorded as a finding; changing protected instructions requires the user's explicit instruction for that action.

### D06 — Medium: the new abbreviated module walkthrough cannot run from a clean state

`modules/README.md:26` enters showcase without registering/selecting a project, then calls `sample-write`. `data/__init__.py:8` requires a project. The longer showcase walkthrough supplies one. This is a defect introduced by the partial layout/documentation change and remains unfixed during the freeze.

### D07 — Technical discrepancy: XML library choice differs from the recorded decision

WF-02 and the decision ledger select ElementTree; `modules/workflows/formats.py:6` uses `minidom`. Existing round-trip checks cover useful preservation cases. This discrepancy is not evidence that all conversion is broken, but it must be reconciled rather than calling the implementation identical to the selected approach.

### Decisions still open

The loader currently rejects duplicate command names across all loaded modules (`plugin_runtime.py:198`), even though modules have contextual menus. Two modules cannot independently contribute `run`. The sources do not settle how such commands should appear at the base menu. This is an extensibility decision, not a justification to silently remove collision checks or declare global uniqueness part of the product.

Step/workflow selector precedence and canonical workflow-tag alias mapping also remain explicitly open in the decision ledger. The final XML versus incremental-intake completion mapping remains open under ledger C05 and `IMPLEMENTATION-PLAN.md:403`. These are unresolved representation/execution mappings, not an invitation to add new answer-content gates. A requirement can be identified as incomplete without inventing its unresolved semantics.

Explicit cross-project reads also need a consistent documented surface: `data.namespace_store().resolve` permits the own/shared scopes described in the API guide, while `data.resolve` opens the project named by the supplied reference directly. Project ownership is retained; the requirements do not establish a blanket prohibition on explicit cross-project reads. This is a scope-contract inconsistency, not a demonstrated authorization violation.

## 9. Earlier review: what still applies

The [earlier chassis review](chassis-full-code-review.md) evaluated a smaller, incomplete slice. Its conclusions cannot establish the current feature boundary.

| Earlier finding | Current assessment |
| --- | --- |
| F1: old intake EF representation | Current maintained intake parser preserves encounter-specific joins. Older converters remain in the shipped tree, so packaging still exposes the conflicting implementation. |
| F2: code largely outside Git HEAD | Still materially true: much fresh runtime, modules and tests are untracked. The review target is the working tree and captured evidence, not HEAD. No commit was made during this audit. |
| F3: misleading README | The opening authored description is preserved; installation/contract drift remains as documented above. |
| F4: unprotected web reads | Current `WebAuth.protect` wraps the application; token/session access and optional authentication are implemented. The old unauthenticated-endpoint description is no longer the current default path. This is not a new security audit. |
| F5: no schema versioning | Superseded: `storage_schema.py` supplies component versions and transactional migrations used by both current stores. |
| F6: copying initiating `sys.path` | Superseded in the examined path: `runtime_client.py:77` uses `child_python`; `child_process.py` deliberately selects import paths rather than copying incidental `sys.path`. |
| F7: no module API version | Superseded: `Plugin.api_version` exists and runtime activation validates it. |
| F8: mixed packaging/dependencies | Still open, with additional direct evidence in M02/M03/M11. |
| F9: no broker backpressure policy | No additional high-load broker requirement was established. This audit does not add one. |
| F10: Python executes on module import | Remains a documented property of trusted Python modules. Lifecycle ownership and supplied-module import behavior still require disciplined handling. |

## 10. Evidence and its limits

| Evidence | What it establishes | What it does not establish |
| --- | --- | --- |
| New core-only boundary test, observed **1 failure in 1.54 s** | Zero selected modules still package a feature engine | No clean chassis acceptance; test stopped before recipient launch |
| Pre-halt layout check, **53 passed in 77.03 s** | Scoped path-change regression evidence | Module ownership, generated config, all-module removal |
| Earlier mechanics check, **271 passed in 73.50 s** | Behavior covered by the recorded 42 test files | Architecture, semantic intake quality, native Windows/macOS, latest boundary requirement |
| In-memory property-selection diagnostic | Unselected provider knowledge reaches a prompt | Broader live-provider inference quality |
| In-memory data diagnostics | Revisionless content observation, destination-routing defect, ambiguous generation visibility | Recovery under process/disk failure |
| Existing direct-wheel clean-environment checks | The tested custom wheels can execute selected paths and preserve recorded prompt/reference data | Minimal package closure, all build routes, pending-folder fidelity, native platform portability |
| Real Codex Native and Latent runs on code and an authored document procedure | Completed Native materialization and substantive independent Latent answers using the complete retained account | Blanket semantic acceptance: a subtype-interpretation issue is flagged; current modularity violations remain |
| Real Claude assignment-tool run after reauthentication and scoped tool permission correction | Assignment read and headed MCP submit succeeded, with no permission denials | Completed full Native/Latent intake |

The [provider review](../artifacts/chassis-review/provider-mechanics/REVIEW.md) preserves the completed Codex runs: code Native produced six objects and five encounter joins; its Latent pass produced seven substantive findings. Document Native produced five objects and five joins; its Latent pass produced eight findings. The retained outputs provide real reasoning evidence. One code Latent statement associated subtype collection with inheritance and is explicitly flagged for semantic review; completion of the run does not resolve that issue.

The successful Claude tool run is recorded under [provider mechanics](../artifacts/chassis-review/provider-mechanics/claude-assignment-tools/claude/inspection.json). Its submitted response was preserved separately from the harness's later final text. The subsequent authored Native procedure read its source but timed out at about 301.5 seconds; it produced no accepted Native materialization or Latent run. Credentials should not be described as the remaining blocker based on the earlier expired-login evidence.

The historical review archive and wheels predate the final folder transition and Claude permission fix. Their hashes identify those snapshots; they are not interchangeable with this audited working tree. Existing aggregate verification documents also lag the newer provider evidence in places.

## 11. Minimum remediation order and acceptance proof

This order is a review outcome, not implementation performed during the halt.

1. **Reconcile the ownership plan and public contract.** Identify the generic services each feature needs, including inference context, exact reads, direct cooperation, async universal data and portable contributions. Correct contradictory engineering guidance without rewriting authored semantic inputs.
2. **Make module containment real.** Move complete engines and resources to their owners, replace private cross-module imports with public interactions, unify runtime `modules/` policy, and expose command ownership in the menu.
3. **Close provenance and causal-identity defects.** Preserve exactly delivered input revisions and producing occurrences, provide universal inspection, and use the shared inference contract from every interface and event/job route.
4. **Correct the reproduced data/context defects.** Resolve layer-selection leakage, route redistribution, assignment folder binding and portability fidelity while retaining histories.
5. **Unify distribution and platform contracts.** Build only selected implementations/dependencies, preserve pending work and module-generated config, and exercise installed, `python -m` and direct-wheel paths consistently.
6. **Complete the outstanding product journeys.** Use the same services for lexicalization, edited replay, memory lifecycle, Native variants and Latent attachment; verify actual agent behavior separately from mechanical fixtures.

### Required modularity proof

| Journey | Required observable result |
| --- | --- |
| Empty module directory and zero-module wheel | Chassis administration, settings, objects and provenance work; no optional feature engines, commands, resources or dependencies are packaged/imported |
| One `.py` module and one folder module | Both declare settings/help/commands/operations/events through the same contract; folder resources travel with their owner |
| Module-generated configuration | Clean direct wheel creates required config from Python declarations only in writable runtime locations; settings/defaults/glue survive disable and restoration |
| Module menu and context | Owning module and its live commands are visible; entering a nonce/module changes the surface; exit restores the base menu |
| Cooperative object work | Module A sends an object reference to B; B performs nonblocking work and returns an attributable response; inputs and outputs retain exact identity/context |
| Universal async data | Namespace operations use the public async surface without blocking unrelated work or losing producer context |
| Inference trace | Output → exact prompt revision/rendered prompt → binding map → exact consumed inputs → earlier producing steps, including tool-fetched context |
| Failure and unload | Failure is attributed to its module; disabling/removing each shipped module withdraws owned contributions and settles owned work; unrelated modules keep working; retained objects/settings remain inspectable |
| Optional transport and feature providers | CLI remains usable without web/MCP; plain workflow use remains available without knowledge extensions; absent explicitly requested capabilities are reported accurately |
| Platform selection | Unsupported modules are skipped before import; module-contained native assets and dependencies produce accurate compatibility metadata |
| Portable project continuation | Selected project/origin state, exact references and pending files survive transfer without the sender's paths, checkout or environment |
| Teaching contract | Every shipped module explains its construction from the common template; the standalone template covers actual universal objects and inference provenance |

Completion requires evidence for these boundaries and journeys. A green component suite or a folder rename alone cannot establish them.
