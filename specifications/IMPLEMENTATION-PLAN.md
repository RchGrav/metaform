# Metaform Technical Completion Implementation Plan

> **Superseded plan/specification — retained evidence.**
> [REQUIREMENTS.md](REQUIREMENTS.md) is the complete governing contract.
> Its [section 20](REQUIREMENTS.md#20-remediation-instructions) authorizes
> active outside-in remediation, tracked in the [live matrix](REMEDIATION-MATRIX.md).
> The earlier tasks, authority statements, technology choices, open questions and
> completion claims below add no requirements and impose no continuing pause.
> They remain useful as historical implementation and verification evidence.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking. Execution is already authorized; these checkpoints require evidence, not another request for permission.

**Goal:** Deliver one inspectable CLI path from an actual artifact through Native intake, Latent reasoning, selected knowledge, an asynchronous workflow, and a portable result whose exact inputs and producing operations remain recoverable.

**Architecture:** A persistent chassis supplies shared services to removable Python modules. Namespace objects own open typed joins; revision-qualified references connect authored definitions, issued prompts, answers, inference, and provenance across configured stores. CLI, harness, and MCP access use the same operations and assignment context.

**Tech Stack:** Python, Click, SQLite, asyncio, existing file locks, executable wheel entrypoint, and the existing Codex/Claude adapter. Optional web remains a separate ASGI module. This plan does not select a new validation, model, or graph database library.

**Spec:** [Product specification](product/PRODUCT-SPECIFICATION.md), [decision ledger](product/DECISIONS-AND-CONFLICTS.md), [Canonical Intake](Canonical_Intake.xml), [universal namespace clarification](namespace-join-implementation-plan.md), [global data pattern](global-data.md), and the latest user instructions summarized below.

## Global Constraints

- **Current priority is working technical mechanics. Web design and integration are deferred.** Existing HTML, screenshots, and partial editor code do not establish a working integrated UI.
- The universal object has exactly `namespace_address`, `name_length`, and `joins`. A join is open authored content with its own `type`, fields, and references. Storage metadata does not add mandatory domain fields to that object.
- Joins belong to their Receiving Entity. An Encounter Function describes the provider's particular encounter and resides in that RE-owned join. One provider may appear with different EFs in different encounters. The current Canonical Intake supersedes the older element-level single-EF representation.
- The current root name is `asset`. Older `media` spellings in retained sources remain evidence of the authored source; any adaptation is explicit and attributable.
- Namespace position expresses functional specificity. The proper name reverses the last `name_length` components. Names have no invented minimum depth or fixed taxonomy fillers. Type Description stays universal; the actual artifact's Native account retains its particulars.
- Preserve authored prompts, source documents, aliases, fields, folder references, answers, and retained revisions. Do not turn development instructions into runtime prompts. Do not add speculative quality gates for agent answers.
- A submission must carry its issued nonce/header. PID identifies a process; it never establishes agent or assignment identity. Transport initialization metadata is not a substitute for the assignment contract.
- Initial storage is global. Configured project/global and split/unified placement remain physical choices; a join type does not intrinsically own a database. No automatic destructive migration of existing user data.
- Project selection starts with all layers selected; object selectors start at zero and masks at one. Apply the incoming mask before the local selection, in trunk-to-leaf order.
- Actual prompt inputs determine inference provenance. Being browseable or attached does not make a contribution an input to a producing operation.
- Preserve Native understanding when invoking Latent reasoning. Latent receives the complete Native account and reasons without access to the repository's implementation details.
- Agents run asynchronously. Optional features can unload without breaking the chassis or another module. Native Windows, macOS, and Linux are chassis targets; optional modules may declare narrower support before their code imports.
- CLI functionality and executable-wheel use are required independently of web and MCP. No automatic commits, publication, or live-data migration are part of this plan.

## 1. Why this work belongs together

Inference amortization is an investment in the current project. Intake records the artifact's functional understanding; later work can begin from that account instead of repeatedly reconstructing it. Namespace meaning provides stable subjects. Joins retain the specific receiving purposes, encounters, properties, and other contributions. Layers let a task select applicable understanding. Provenance identifies what actually informed an answer, so changed properties can lead to targeted new inference while unaffected work remains useful.

Each delivery below therefore ends in an observable reuse or preservation result. A file converter, graph picture, successful subprocess, or passing fixture alone cannot establish this complete behavior.

## 2. Observed baseline and evidence boundary

This is the September 18 working-tree baseline, not a claim that the full product has shipped. Other workers may complete a slice during execution; update its evidence rather than rebuilding it.

| Area | Observed implementation | Remaining integration |
| --- | --- | --- |
| Chassis | Public services, persistent host, Click context, lifecycle, sync/async operations, events, jobs, settings/glue, TUI, drop-in policy and OS metadata exist. | Verify the same boundaries with real workflow/intake operations and universal provenance. |
| Namespace storage | `NamespaceStore` assembles open joins across files, retains revisions, supports exact refs, selective export/import, and configurable placement. | Production joins/outbox, layer projection, artifact history, and eligible global wheel closure are implemented. Historical producer migration and broader semantic acceptance remain. |
| Workflow objects | Definitions, steps, issuance, arbitrary answers, and provenance are module-owned joins. Manual CLI issue/submit works. | Durable execution includes headed handoffs, real user waits, authored branches/loops, parallel/nested control, and shared CLI/MCP access. Fixture integration covers Native→Latent→inference; model interpretation and semantic acceptance remain distinct. |
| Document authoring | Markdown/XML/JSON retain source structure and aliases. Rich text/tail segments preserve object references and selected layers, including historical revisions. | Source-preserving workflow preparation now runs through the shared engine. Whole-object UI work is deferred; a format conversion alone does not establish correct handoffs. |
| Collected graph | XML importer retains raw source and actual object/join/layer attachments, including historical attachment refs. | This is collected-data projection, not an inference or layer-applicability engine. |
| Harness demos | Standalone showcase and two template-derived event modules exist; jobs return later through the event bus. | Harness execution now routes shared workflow assignments; broader real-model semantic acceptance remains. |
| Distribution | Selected-module/project wheels include retained payloads and pending assignment restoration; executable wheel-to-wheel rebuilds are tested. | Focused wheel tests cover dependencies, pending continuation, origins/variants, eligible global closure, and rebuild. Native cross-platform execution and substantive provider acceptance remain separate. |
| Legacy code | Earlier intake, MCP, graph/layers, file history, and workflow implementations remain in the package. | Their existence/tests do not establish migration of old stored data to the new object mechanics. |
| Web | Optional web, graph/editor/auth/terminal work exists in several stages. | Deferred. Live HTML is not integrated JavaScript evidence. |

Recorded verification has limited scope: [chassis verification](../docs/chassis-verification.md) reports an earlier 86-test Linux foundation run and a wheel walkthrough; its real Codex/Claude checks were greetings. During the subsequent document work, 27 focused conversion/workflow tests passed, including rich-reference round trips; 37 compatibility-related tests passed earlier. These are historical component observations. **Fresh scoped integration:** 32 tests passed across `test_artifact_history.py`, `test_workflow_execution.py`, `test_system_intake.py`, `test_namespace_layers.py`, and `test_universal_provenance.py` in 9.25 seconds. The distribution implementer separately reported 10 distribution/contextual-CLI tests passing, including retained origin/variant reconstruction after executable-wheel transfer and wheel-to-wheel rebuild. These are component/integration checks, not full-product completion. Final claims require the journeys in section 6 against the delivered artifact.

**September 18 documentation-linked check:** 70 tests passed in 87.31 seconds across
namespace storage/CLI/relocation, rich document round trips, workflow objects/preview,
internal intake, fixture Native→Latent→inference, layers, native control, and seven-source
workflow preparation. The exact command is in [verification](../docs/chassis-verification.md).
Checked items below name their corresponding behavior; this run is not authenticated
model semantic acceptance or a final distribution build.

**Final current backend suite:** the selected 42-file run passed **271 tests in
73.50 seconds**. Its [command/file list](../artifacts/chassis-review/mechanics-verification/final-tests.json)
and [log](../artifacts/chassis-review/mechanics-verification/pytest-final-mechanics.log)
cover current chassis/namespace/workflow/harness/MCP/layers/history/distribution
mechanics, including shared global inputs, MCP metadata/PID fixes, and assigned
incremental-write provenance. Web presentation is excluded. Earlier 268-test and
focused follow-up results are retained in verification; counts overlap. Semantic
acceptance and the repository-wide result remain separate.

**Repository-wide result:** `.venv/bin/python -m pytest -q -n 4 --tb=short tests`
reported **1,186 passed, 98 failed, 8 errors, 1 xfailed in 179.92 seconds**.
[Failure classification](../artifacts/chassis-review/mechanics-verification/failure-classification.md)
accounts for earlier CLI/App contracts, service fingerprint failures, old intake
expectations, a timing case, and deferred web presentation. No current backend
regression was identified in that audit; the full suite remains red. This is not
substituted with focused passing counts.

**Selective regeneration:** the implementer's 12-test workflow/regeneration/runtime
run passed in 71.09 seconds; after exact-target-revision and general-visibility
repairs, the regeneration/intake-inference subset passed 2 tests in 62.21 seconds.
`regeneration.py` selects completed subjects by transitive recorded causal inputs;
`targets` and `changed_refs` do not schedule work automatically. Stable subject
attachments revise within a recipe lineage while older revisions remain available.

**Delivered wheel evidence (10:27 UTC):** both builds in the
[final manifest](../artifacts/chassis-review/final-20260918T102728545085Z/manifest.json)
passed isolated `python -S` checks after the final MCP/global-input repairs. The
MCP variant exercised controlled-provider stdio assignment/submit/complete. Both
rebuilt a pending project, preserved its nonce/header in a fresh recipient, and
completed A→B with exact output refs and pinned shared revision 1. All 227 CLI/
229 MCP captured source files matched; four smoke/transfer hosts stopped. Hashes
and exact scope are in [verification](../docs/chassis-verification.md).

### Existing public contracts to reuse

```python
from metaform import settings, event, cli, data, work, modules

NamespaceObject(namespace_address: str, name_length: int, joins: list[dict])
JoinRef(project: str, namespace_address: str, join_id: str, revision: int)

NamespaceStore(project, databases, routes=None, default_database=None)
store.ensure(address, name_length)
store.get(address, join_types=None)
store.list(scope='')
store.put_join(address, join, name_length=1, database=None)
store.resolve(ref)
store.export(scope='', join_types=None)
store.import_export(document, database=None)

# A module obtains its project-bound store through this public service.
data.namespace_store()

WorkflowEngine(store).create(address, steps, name_length=1,
                             join_id=None, source_document=None)
WorkflowEngine(store).preview_segments(segments, bindings=None)
WorkflowEngine(store).issue(workflow_ref, step_id, bindings=None)
WorkflowEngine(store).submit(issued_ref, answer)
WorkflowEngine(store).inspect(ref)
WorkflowEngine(store).retain_source(address, document, name_length=1, join_id=None)

work.assign(prompt, **metadata)
work.submit(header, answer, nonce=None)
work.submit_job(operation, **arguments)
event.publish(topic, refs=())
event.subscribe(topic, handler)
cli.invoke(operation, **arguments)
```

Core `production_joins.py` now mirrors current producing operations through a durable outbox; earlier rows remain readable legacy data. Core `namespace_layers.py` now supplies selectors, masks, visibility, and property projection over owned joins. Async service counterparts already exist; use them inside async callbacks instead of blocking the event loop. `data.put/get/provenance` keep compatible Record/Producer return surfaces while new writes use production joins. This does not establish migration of all historical rows.

Rich native segments are authored text `{text}` or an object insertion `{binding, namespace_address, contributions: [JoinRef], layer_select}`. Imported document nodes optionally carry `text_segments` and `tail_segments`; those arrays are authoritative when present. Scalar `text`/`tail` retain only authored plain text. XML metadata and annotated Markdown preserve references without flattening generated context into authored text.

## Initial delivery targets

The first delivery covers four connected outcomes: complete universal-object authoring, actual-source intake, selected inference with exact producing provenance, and an executable project wheel. These are delivery groupings of the agreed requirements, not additional product rules. Shared workflow execution, nonblocking harness/MCP access, and preserved artifact history connect those outcomes. All four require the journeys below; component tests alone do not mark them delivered.

## 3. Execution order and ownership boundaries

Tasks 1–3 stabilize contracts already present. Tasks 4–6 create the shared execution path. Tasks 7–9 supply actual intake and reusable inference. Tasks 10–12 deliver preserved variants and portable continuity. Task 13 verifies the complete product. Independent owners can work in parallel only with explicit file ownership; a task's tests must consume the preceding contract rather than implement a second engine.

Proposed new file paths below are implementation assignments, not claims that those files already exist or that their names are domain requirements. Existing files are authoritative for signatures. If ongoing work already supplies a proposed responsibility, extend that implementation and record the path adjustment here.

### Task 1 — Preserve the semantic and source contract

**Why:** Reusing a recorded account only helps when it retains the intended meaning and the source that produced it.

**Files:** `specifications/Canonical_Intake.xml`, `specifications/product/DECISIONS-AND-CONFLICTS.md`, `examples/plugins/web/graph_data.py`, `tests/test_intake_graph_data.py`; runtime definition files are introduced in Task 7. Read [Name](../docs/rulebook/element/name.md) and [Description](../docs/rulebook/element/description.md).

- [x] Retain two receiver-owned encounters with one provider and distinct OP/EF fields, source refs, and export history (`test_system_intake.py`, `test_intake_inference_runtime.py`). No EF is synthesized on the provider.
- [ ] Exercise names with reused ancestry and differing `name_length`; retain every source attribute, combined/subtype detail, unknown field, and raw answer.
- [ ] Record explicit source adaptations required by current instructions (`asset`, encounter-specific EF) alongside source revision. Do not silently rewrite the authored source or apply a global lexical blacklist.
- [ ] Document the concrete adapter between Canonical XML fields and open joins, retaining original field names. Address only the genuine residual source discrepancies in section 5.
- [ ] Run `tests/test_intake_graph_data.py` and inspect the resulting fixture joins against the source, not just expected counts.

**Acceptance:** An imported encounter is traceable to its actual source bytes and its RE; shared-provider encounters remain distinct through round trip. No display adapter invents a relationship or a new semantic namespace as an opaque source ID.

### Task 2 — Close namespace authoring and storage behavior

**Why:** Knowledge must remain an independently editable and referable contribution even when storage moves or a later prompt selects a different subset.

**Files:** `src/metaform/namespace_objects.py`, `namespace_store.py`, `namespace_service.py`, `contextual_cli.py`; `tests/test_namespace_store.py`, `test_namespace_cli.py`, `test_namespace_services.py`, `test_namespace_relocation.py`, `test_namespace_targets.py`.

**Interface:** Preserve the exact three-field object and four-field `JoinRef` above. Join IDs supplied by authors survive; generated UUID IDs are the present reversible default. Same identity/revision and same content deduplicate; divergent content reports a conflict and retains the source for resolution.

- [ ] Inventory existing CLI get/list/put/export/import operations, then add only missing whole-object authoring and inspection behavior with failing behavioral tests first. Editing a join creates a new revision; references already issued continue resolving the earlier revision.
- [x] Exercise more-than-attachment-limit placement and concurrent retained revisions (`test_namespace_store.py`). Multi-store reads do not require one attached SQLite connection.
- [x] Round-trip authored lookalike dictionaries, typed refs, paths, open content, and exact historical revisions (`test_namespace_store.py`).
- [x] Verify selective export retains selected history and unresolved references without inventing closure (`test_namespace_store.py`). Full missing-reference/eligible-closure reporting remains Task 12.
- [x] Exercise all four storage modes and relocation while retaining exact refs and original files (`test_namespace_cli.py`, `test_namespace_relocation.py`).
- [ ] Define and test interrupted-copy retry and concurrent read/write behavior within the current lock model. Document that several SQLite files are not one crash-atomic distributed transaction.

**Acceptance:** The same object can be inspected and edited from CLI before and after every placement change. Old refs resolve identically; no physical database name changes semantic ownership.

### Task 3 — Complete reusable workflow authoring mechanics

**Why:** Preserved authored steps and pinned inline inputs let later workflows reuse project understanding without losing what a prior prompt actually received.

**Files:** `examples/plugins/workflows/{__init__,engine,formats}.py`, `formats.md`, `README.md`; `tests/test_workflow_objects.py`, `test_workflow_formats.py`, `test_document_object_roundtrip.py`, `test_workflow_preview.py`.

**Interfaces:** Reuse `WorkflowEngine` and the rich segments above. Preview is read-only; issue creates an immutable rendered prompt and actual inserted references. `workflow.output.answer` supplies output text, explicit join `text` supplies collected text, and other structured content retains a JSON representation.

- [x] Verify mixed rich-segment Markdown/XML/JSON round trips, attributes/aliases, and pinned revisions (`test_document_object_roundtrip.py`).
- [x] Verify sibling reorder/rename and visible Markdown text edits retain source IDs and rich reference ownership (`test_document_object_roundtrip.py`).
- [ ] Provide complete CLI operations to inspect/edit the retained document and native definition. Keep source document identity linked when semantic intake later produces executable steps.
- [x] Issue A→B→C through CLI, preserve earlier prompts across source changes, and round-trip the chain (`test_workflow_objects.py`).
- [x] Verify read-only preview and actual-input provenance (`test_workflow_preview.py`, `test_workflow_objects.py`).

**Acceptance:** The chain's final output can be followed to the exact prior outputs, issued prompts, source documents, and selected contribution revisions entirely through CLI. Conversion alone claims no semantic workflow interpretation.

### Task 4 — Connect producing operations to universal provenance

**Why:** Exact dependency records make retained understanding auditable and identify which reasoning needs reconsideration after a project changes.

**Files:** `src/metaform/production_joins.py`, `plugin_store.py`, `plugin_runtime.py`, `assignments.py`, `work.py`, `data/__init__.py`; `examples/plugins/workflows/engine.py`; `tests/test_workflow_execution.py`, `test_universal_provenance.py`, and `test_intake_inference_runtime.py`.

**Interface:** Each produced output resolves to its producing operation, prompt revision, exact rendered prompt, binding map, actual input revisions, and actual answer. Those are module-owned open join contents; they do not add fields to `NamespaceObject`. Preserve existing public compatibility until an explicit replacement is implemented.

- [x] Connect workflow issuance/output to headed chassis assignments and producing refs (`test_workflow_execution.py`, `test_workflow_runtime_path.py`, universal-provenance tests).
- [x] Publish current producer/output/provenance joins through the durable `production_joins` outbox. Five universal-provenance tests verify reads independent of stale producer indexes, exact dependencies, split-store replay, rollback, and assignment snapshots. Historical row migration remains below.
- [ ] Retain failed/cancelled operation diagnostics and actual partial responses without inventing successful answers. Preserve actual answers even when interpretation fails.
- [ ] Verify two projects and two parallel assignments cannot acquire each other's producer context through events, threaded callbacks, or async task switching.
- [ ] Add a copy-based migration/export adapter for earlier Record/Producer tables only after new writes work; verify counts, contents, and reference mapping before activating the new copy. Keep originals and a readable migration report.

**Acceptance:** A final workflow answer leads to an actual producing operation through universal refs; an operation's browseable but unused records never appear as causal inputs. Existing data is neither silently dropped nor claimed migrated by a new label.

### Task 5 — Run workflows through one durable asynchronous path

**Why:** Recorded context becomes useful project infrastructure when agents can execute and resume authored work without rebuilding state in each client.

**Files:** `examples/plugins/workflows/engine.py`, `__init__.py`; `examples/plugins/workflows/execution.py`; `src/metaform/{work,assignments,plugin_runtime,runtime_client,runtime_server}.py`; `examples/plugins/harness_runner/adapter.py`; new `tests/test_workflow_execution.py`.

**Current interface:** `WorkflowExecution(store, project, module="workflows", working_dir=None)` exposes `start(workflow_ref, inputs=None, layer_select=None)`, `inspect(run)`, `advance(run)`, `answer_user(run, step_id, answer)`, and asynchronous `drive(run, driver=...)`. It uses existing issuance/assignment/submission services. Focused execution tests reopen Store at every handoff, prove headed answers become subsequent exact prompt inputs, preserve explicit parallel dependencies and real user waits, and demonstrate background completion. The native control implementation now adds branches, loops, parallel/foreach, nested calls, tools, deadlines, and authored retries; `test_workflow_control.py` covers its retained execution behavior. Interpretation correctness remains separately reviewable.

- [x] Verify background execution, dependent handoffs, and completion events through the shared runtime (`test_workflow_execution.py`, `test_workflow_runtime_path.py`); separate-client host persistence is covered by chassis tests. Final delivered-wheel acceptance remains Task 13.
- [x] Persist run, definition, step, issued, assignment, and output refs with project/module/nonce context (`test_workflow_execution.py`, `test_workflow_runtime_path.py`).
- [x] Reuse previously issued prompts and completed outputs across replay, retain authored retry attempts, and serialize coordinators (`test_workflow_execution.py`, `test_workflow_control.py`).
- [x] Provide explicit resume and durable handoff replay; retain interrupted tool outcomes without repeating their side effect (`test_workflow_control.py`, `test_workflow_execution.py`, portable assignment tests).
- [ ] Complete exhaustive process-crash injection at every external launch/response boundary; existing replay tests do not establish every crash window.
- [x] Execute authored user waits, branches/loops, parallel/foreach, nested calls, and tool/retry/deadline control through the retained native definition (`test_workflow_control.py`). Preparation uses the packaged grammar; XML tags alone do not select behavior.
- [x] Verify running harness cancellation/unload/shutdown and retained partial provider diagnostics using `test_demo_templates.py` and chassis job/shutdown tests. End-to-end semantic work remains separately assessed.

**Acceptance:** Work survives the submitting client, completes without blocking it, and can be followed step by step from a fresh CLI. Exactly one authored next step advances for one accepted completion.

### Task 6 — Share the assignment contract with MCP and harnesses

**Why:** Any compatible agent should receive the same assignment and reusable knowledge without depending on a particular harness's process layout.

**Files:** `src/metaform/{assignments,work,contextual_cli,navigation}.py`, `mcp_server.py`, `portable_mcp.py`; implemented `src/metaform/chassis_mcp.py` and external `examples/plugins/mcp/__init__.py`; `tests/test_chassis_mcp.py` and existing chassis CLI/job tests.

**Interface:** Existing issued header is `{assignment, nonce, step}`. `Assignments.issue/begin/submit/finish/track_process` and workflow issuance must point to the same work. MCP is an optional adapter over shared operations, never an alternative workflow scheduler.

- [x] Demonstrate interleaved distinct nonces in one MCP process without context crossing (`test_chassis_mcp.py`).
- [ ] Complete the explicit two-MCP-processes/one-assignment acceptance case.
- [x] Expose assignment/status, exact prompt/context reads, project namespace/exact-ref reads, owning-module calls, and headed answers through current MCP and CLI (`test_chassis_mcp.py`).
- [ ] Complete dedicated structured object-write ergonomics where owning-module operations are insufficient; no second scheduler is needed.
- [x] Reject missing/crossed headers before submission and retain arbitrary correctly headed answers (`test_chassis_mcp.py`, chassis assignment tests).
- [x] Record transport/harness PIDs by nonce and role; one MCP process serves distinct assignments (`test_chassis_mcp.py`, provider process evidence).
- [x] Verify contextual nonce help, hidden command unavailability, and matching marker cleanup through the current chassis menu/assignment and MCP tests.
- [ ] Run fixture, Codex, and Claude through the same operations. Exercise both direct harness launch and an already-running agent entering its assigned nonce; retain real prompts/answers as evidence when providers are available.

**Acceptance:** A CLI-created assignment can be completed through MCP and an MCP-created assignment through CLI, with identical exact-input/output provenance and clean navigation. Any provider availability limitation is recorded honestly.

### Task 7 — Execute maintained Native and Latent intake workflows

**Why:** This creates the project's reusable functional account; the Latent pass can then reason from the complete account without being absorbed in implementation details.

**Files:** internal `src/metaform/system_workflows.py`, `src/metaform/intake_documents.py`, and `src/metaform/data/system_workflows/Canonical_Intake.xml`; external `examples/plugins/workflows/execution.py` supplies the shared execution engine; `tests/test_system_intake.py` and `tests/test_intake_inference_runtime.py`. Intake stays internal: it is not a separate feature module. Read Canonical Intake, product INT-01–09, and [artifact intake semantics](../docs/semantics/artifacts-and-functional-intake.md).

- [x] Preserve the exact Canonical Intake bytes as an internal packaged workflow source. `system_workflows.native_definition(artifact_ref)` and `latent_definition(native_ref)` produce ordinary shared-engine definitions; `intake_documents.import_namespace_result(store, xml_text, source_ref)` retains actual answers and encounter-owned joins. Five focused component tests were reported passing by the intake implementer; actual-source end-to-end acceptance remains below.
- [x] Run actual Codex Native against an isolated copy of `namespace_objects.py`; retained evidence includes source bytes/hash, provider PID/cwd, Canonical prompt, XML, and materialized objects (`provider-mechanics/REVIEW.md`).
- [x] Obtain substantive non-code Native output: the later Codex `dual_agent.md` run completed in 282.699 seconds with five objects/five encounter joins, including distinct EFs from a shared provider to two REs (`provider-mechanics/mcp-bridge/authored-procedure/codex-native/inspection.json`). Full authored-semantic acceptance remains review work; the earlier authentication/bounded failures stay recorded.
- [x] Retain actual answers, original XML, partial diagnostics, and distinct encounter-owned EFs for a shared provider (`test_system_intake.py`, fixture process integration in `test_intake_inference_runtime.py`).
- [x] Provide nonce-bound CLI `namespace put-join` producing provenance parented to the assignment, retaining exact prompt/authored contribution while leaving the assignment open (new `test_namespace_cli.py` regression). Final answers remain separately retained.
- [ ] Complete the authored final-vs-incremental delivery mapping and any needed MCP incremental-write surface; one partial object must not mark the whole intake complete.
- [ ] Capture recursion from DE through the receiving OPs, requirements, properties, and supportive encounters as authored. Preserve combined/annealed addresses, valid inactive subtype addresses, and retained source detail; do not manufacture decomposition to satisfy counts.
- [x] Deliver the complete retained Native account in a fresh Latent workfolder and retain its answer separately (fixture integration and actual provider evidence). A fresh workfolder is not an OS sandbox.
- [x] Obtain substantive code Latent reasoning using maintained `latent-task.md` plus exact role/full Native account: seven object/join findings in 126.883 seconds (`provider-mechanics/mcp-bridge/code-records/codex-latent/inspection.json`).
- [x] Complete the actual document Latent run with the full Native account in a fresh workfolder; eight substantive findings are retained (`provider-mechanics/REVIEW.md`).
- [ ] Complete authored-semantic acceptance review. The code answer contains a flagged subtype/inheritance claim; successful delivery is not blanket typological acceptance.
- [x] Provide source-preserving preparation through shared workflow execution (`preparation.py`, `test_workflow_preparation.py`). Model interpretation and lexicalization quality remain semantic acceptance work.
- [ ] Exercise the seven supplied workflow sources (`orchestrator`, `multi_agent_orchestrator`, `dual_agent`, `extractor`, `metaprompt`, `taskeengineplus`, and `python_to_c`) through preservation and interpretation. Retain their distinct authored steps and decisions; a successful conversion of one generic fixture does not establish their execution.

**Acceptance:** Inspect two completed assignments from real intake: Native demonstrably had the actual artifact; Latent demonstrably had all Native understanding and no repository implementation access. Review semantic fidelity against the source separately from transport/test success.

### Task 8 — Resolve selections, masks, visibility, and properties

**Why:** A task can reuse the relevant knowledge while changes to a property affect the correct parts of the project and do not contaminate unrelated branches.

**Files:** implemented core `src/metaform/namespace_layers.py`; workflow preview/issue integration; `tests/test_namespace_layers.py` and additional end-to-end layer tests. Read product KG-01–10 and the latest selection decisions; inspect earlier `src/metaform/layers.py`/`properties.py` for reusable algorithms without importing their old record model.

**Selection contract:** For a finite set of known layer identities, equivalent set/bit behavior is:

```text
incoming = project_selection_or_explicit_workflow_selection
for object in path_from_trunk_to_leaf:
    selected = (incoming AND object.layer_select_mask) OR object.layer_select
    incoming = selected
```

Defaults are project selection = all known layers, local selection = none, mask = all known layers. Local selection can reselect a layer blocked by an ancestor. Layer IDs remain stable when more layers arrive; storage encoding is an engineering choice. Workflow selection observes the same object masks. Visibility dependencies apply after selection; a selected layer cannot restore hidden source-derived content by accident.

Here `object.layer_select` and `object.layer_select_mask` are pseudocode for the selectors read from that object's owned typed joins. They are not additional fields on `NamespaceObject`.

- [x] Verify defaults, ancestor masks, local reselection, explicit workflow selection, and new layers through `test_namespace_layers.py`; the implemented selector uses stable namespace names plus a `*` default.
- [x] Keep general browsing defaults separate from workflow masks/selection and pin effective inputs in issued assignments (`test_namespace_layers.py`, `test_workflow_execution.py`); regeneration preserves an existing general=false flag.
- [x] Derive current visibility from retained exact input refs. Layer tests verify transitive hidden-source effects, cycles, project scope, and preservation of historical bodies and independent knowledge. Fixture process integration now verifies object/join inference attachments in `test_intake_inference_runtime.py`; semantic quality still needs review.
- [ ] Separate a newer source revision from hiding a source: report staleness against exact inputs without silently deleting, rebinding, or automatically rerunning the prior generation.
- [x] Implement branch property applicability and ancestor summaries in `Layers.property_context`. Tests verify installer Bash and engine C++ reach their own descendants and the trunk summary without leaking into siblings; soft properties stay local.
- [x] Resolve masks and selected inputs during issuance and retain their exact revisions (`test_workflow_execution.py`); fixture inference verifies selected attachments and independent hidden-source behavior.

**Acceptance:** A project and a workflow obtain predictable selections from the same masks; branch properties do not leak sideways; hidden-source inference disappears from current use and remains inspectable historically.

### Task 9 — Produce reusable inference and memory layers

**Why:** Object-specific reasoning and memory can be reused in later task frames, and the exact recipe makes necessary new inference targeted rather than a complete rediscovery.

**Files:** `examples/plugins/workflows/regeneration.py` selects affected prior subjects; `examples/plugins/knowledge/__init__.py` supplies memory and layer operations; `examples/plugins/workflows/operations.py` supplies `infer`/`reinfer`; `src/metaform/namespace_layers.py` resolves context; `tests/test_intake_inference_runtime.py` and layer tests cover the joined path. `tests/test_workflow_runtime_path.py` verifies memory as selected context with its actual source; dedicated search/edit ergonomics remain open. Earlier knowledge-tool, layer-generation, and blindspot prompts are source material, not an automatically approved rewrite of current semantics.

- [x] Expose authored inference over scoped objects and their owned joins, with exact Native-generation targeting, property context, and join-specific attachments (`test_intake_inference_runtime.py`). Automatic changed-property target selection remains open.
- [x] Issue per-target work through the shared background runtime and retain actual outputs as layer attachments. `operations.infer` records the recipe and `drive` emits shared progress/completion events; fixture process integration verifies returned jobs, exact prompts, and attachments. Authored grouped work is not inferred automatically.
- [x] Create namespace-indexed memory with exact source refs and a selected layer attachment (`test_workflow_runtime_path.py`); retrieve/inspect it through knowledge and namespace services.
- [ ] Complete dedicated memory search/revision ergonomics; ordinary owned-join revision support already retains history.
- [ ] Exercise a best-practice layer, a task-specific imperative layer, and agent-authored memory on the same object; preview shows only selected applicable contributions and exact knowledge addresses remain browseable.
- [x] Select changed-input dependents using `reinfer changed_refs` and optional exact targets; preserve unaffected attachments and old revisions, link recipe lineage/generation, and keep existing general visibility (`test_workflow_regeneration.py`). Supplied new target revisions are honored; missing targets report an error.

**Acceptance:** A second independent workflow starts from recorded project knowledge/memory and its provenance shows those exact inputs. Inspectable records establish reuse; token savings may be measured but are not invented as a benchmark claim.

### Task 10 — Preserve ports, artifact variants, and reconstruction

**Why:** A changed medium or a new candidate should reuse unaffected understanding while retaining every produced alternative and the reasoning that made it.

**Files:** implemented core `src/metaform/artifact_history.py` and external `examples/plugins/history/__init__.py`; proposed inference-variant module `examples/plugins/variants/{__init__,engine}.py`; `src/metaform/history.py`, `workfolders.py`, `portable.py` as compatibility sources; global-data specification; `tests/test_artifact_history.py`, plus future `tests/test_namespace_variants.py` for semantic port behavior.

- [ ] Clone a project's Native interpretation with explicit origin/variant identity and original refs. Change a scoped property; derive affected inference from applicability and actual producing inputs rather than replacing all knowledge.
- [ ] Run the supplied port scenario: remove selected C++ context, attach authored C++→C# port guidance and C# knowledge, generate per-object/join guidance, then hide the temporary port object. Its dependent current inference detaches; retained provenance remains.
- [x] Reissue original recipes for explicit changed causal inputs, retaining unrelated subject attachment identities/revisions and older answers (`test_workflow_regeneration.py`). This does not clone a Native interpretation.
- [x] Retain full origin identities and report divergent compatible histories as distinct suffix lineages; preserve exact join IDs (`test_artifact_history.py`).
- [x] Retain sibling artifact variants with exact supplied producing references; reconstruct text changes, added/deleted/renamed paths, directories/symlinks, and changed binaries in Python with hash checks and no Git retrieval dependency. The CLI records its collecting operation when no generating producer is supplied. Eight artifact-history tests cover these mechanics; actual agent-generated artifact provenance remains an end-to-end check.
- [x] Export captured origins, variants, exact namespace revisions, and payload bytes; reconstruct after executable-wheel transfer and rebuilding that wheel. Explicit commit capture reads committed bytes, including a selected repository subfolder. Re-anchoring is explicit.
- [ ] Complete earlier history migration and the broad continuation acceptance journey. Pending assignment/workfolder restoration and explicit continuation now have focused wheel tests; retained artifact bytes alone are not that evidence.

**Current artifact service:** `ArtifactHistory(root, namespaces)` exposes `capture_origin(address, source, base_commit=None, producer=None, name_length=1)`, `collect_variant(origin_ref, folder, producer=None)`, `reconstruct(ref, destination)`, `export(namespace_document=None)`, and `import_export(document)`. Payload export consumes an optional already-captured namespace snapshot, supporting the builder's single selected view. Divergent compatible artifact history creates a separate lineage membership join/new suffix, while exact namespace-version conflicts still fail without rewriting supplied IDs. See [history module guide](../modules/history/README.md).

**Acceptance:** Two variants and a port's knowledge can be independently reconstructed/inspected; none erase the origin or each other. A meaningful provider response is reviewed for changed guidance separately from fixture proof of correct routing.

### Task 11 — Close chassis lifecycle, menus, and teaching surfaces

**Verified review repairs:** Direct async operations now receive cancellation during
runtime shutdown; synchronous workers settle before teardown. An operation or job
can initiate shutdown without awaiting or cancelling its own stack. Shutdown rejects
new events while allowing active stop hooks and their awaited response handlers to
finish their event exchange. A focused 86-test integration run passed across shutdown,
module API/OS compatibility, discovery, jobs, shared host, settings/TUI, namespace
storage, schema, and universal provenance. Python threads cannot be forcibly killed:
a synchronous callback that never returns can still delay shutdown, as documented
by the worker-settlement contract.

`PLUGIN_API_VERSION = 1` and trailing `Plugin.api_version=1` retain existing modules;
incompatible contracts are isolated before activation/hooks. Store and NamespaceStore
now have independent transactional schema markers and migration callbacks, with
unversioned-table preservation and failed-migration rollback verified. Earlier
architecture records and module-owned auxiliary tables are not silently migrated.

**Why:** Stable public hooks let community modules participate in the same recorded execution without depending on internal tables or a particular front end.

**Files:** `src/metaform/{plugin_contract,plugin_runtime,plugin_policy,module_metadata,module_catalog,settings,event,work,contextual_cli,navigation,tui}.py`; `examples/plugins/{showcase,event_requester,harness_runner}/`; `docs/plugin-api.md`; existing chassis/discovery/compatibility/demo tests.

- [x] Verify the standalone teaching hooks through the recorded foundation walkthrough and demo tests: settings/commands, sync/async operations/events, jobs, data/provenance, assignments, and lifecycle. Template extension remains continuous maintenance, not an unimplemented initial demo.
- [x] Keep the three teaching modules and verify their request/result event exchange (`test_demo_templates.py`). Harness/requester carry template support so either can be packaged independently of an installed showcase.
- [x] Verify marker-based module/nonce menus, matching cleanup, current help, and command availability (`test_chassis_menu_product.py`, recorded separate-process walkthrough).
- [x] Verify Python-owned help/settings, staged TUI glue/reset, and unload/re-enable retention (`test_chassis_tui.py`, `test_chassis_setting_glue.py`; included in the 86-test review run).
- [x] Verify drop-in discovery, authoritative disabled policy, and pre-import OS exclusion with peer isolation (`test_plugin_discovery.py`, `test_module_compatibility.py`; included in the 86-test review run).
- [x] Verify shared-host reuse, interrupted jobs, module/subscription withdrawal, owned process cleanup, and shutdown (`test_shared_runtime.py`, `test_chassis_jobs.py`, `test_runtime_shutdown.py`, demo provider cancellation tests).
- [x] Supply `metaform skill` from the current context-aware help/assignment surface; launch-local MCP configuration carries nonce and producer without changing global harness settings.
- [ ] Complete first-run/provisioning onboarding once mapped in section 5. Runtime guidance stays separate from expert development instructions.

**Acceptance:** A reviewer can use the three examples to build/remove another module through the documented contract. Linux evidence is labelled Linux; simulated Windows compatibility is not a native Windows test.

### Task 12 — Deliver selected-project executable wheels

**Why:** The project retains its accumulated understanding and can continue work away from the original checkout, service, and machine.

**Files:** `src/metaform/distribution.py`, `src/metaform/distribution_closure.py`, `examples/plugins/distribution/__init__.py`, `tools/build_distribution.py`, `packaging/__main__.py`, `src/metaform/child_process.py`, `pyproject.toml`; `tests/test_distribution.py`, `tests/test_child_import_paths.py`; pending continuation and wheel rebuild checks live in `tests/test_distribution.py`. Coordinate with ongoing builder work before editing.

**Interface:** The existing distribution module accepts selected modules, an optional project, explicit source inclusion, and selected installed dependencies, with platform tags/extraction for native dependencies. The builder uses `distribution_closure.capture` for eligible global exact-reference dependencies and reports unresolved/foreign references. Direct namespace scope exports remain literal selection.

- [x] Build selected-project wheels with exact eligible global dependencies, retained source/workflow/history bodies, module resources, and pending assignments (`test_distribution.py`; builder evidence recorded in verification).
- [x] Consume explicit shared `@metaform` inputs/definitions through the project-bound service, preserve actual global owner controls and exact refs, and exercise recipient-wheel prompt/layer resolution (`test_shared_workflow_context.py`, targeted distribution regression). Raw stores stay single-project and unrelated project reads remain excluded.
- [x] Verify cyclic/exact global closure, identity-only NamespaceRefs, historical revisions, provenance mirrors, and unresolved/foreign-project reports without importing unrelated projects (`test_distribution.py`).
- [x] Capture project and eligible global snapshots under the shared namespace layout lock (`test_distribution.py`). Public namespace writes participate; direct raw-store/external SQLite writes bypass this boundary.
- [ ] Complete explicit interrupted-export retry acceptance; multiple SQLite files are not a distributed transaction.
- [x] Verify executable/installed wheels, child import paths, native MCP dependencies, and self-contained harness/requester template support in isolated recipients (`test_distribution.py`, `test_child_import_paths.py`, demo-template tests).
- [x] Launch both delivered archive entrypoints under `-S` and blank import/tool paths in isolated roots; rebuild a pending project, preserve its assignment in a fresh recipient, and complete A→B with pinned shared revision 1 (`final-20260918T102728545085Z` evidence). Component tests separately reconstruct retained variants and rebuild again.
- [x] Complete the transferred fixture chain through its final downstream answer. Actual Codex Native/Latent and real MCP assignment-read evidence are retained separately; fixture success does not establish semantic correctness.
- [ ] Run equivalent installed entrypoint operations and native Windows/macOS/Linux checks where available. A platform-specific optional module is skipped with a useful reason; the remaining chassis works.

**Acceptance:** The returned artifact can continue a real selected project without the source installation or Git. Record binary/provider prerequisites explicitly; verified MCP dependency bundling is not a claim that every third-party native dependency is portable.

### Task 13 — Verify and archive the complete mechanics

**Files:** tests from Tasks 1–12; `docs/chassis-verification.md`; `artifacts/chassis-review/verification.json` and referenced logs; existing `artifacts/chassis-review/build_review_bundle.py`.

- [ ] Execute the journeys below against a fresh isolated root and the final wheel. Retain command inputs/outputs, exact refs, source/response bytes, artifact hashes, and process cleanup evidence.
- [x] Run focused mechanics suites and the full repository suite; retain the red full result and classify every failure/error separately. Current counts and exact commands are in `docs/chassis-verification.md`.
- [ ] Review prompt/source fidelity and actual Native/Latent/inference answers against their authored requirements. Record semantic observations separately from routing/storage assertions; no invented rejection gate is added.
- [ ] Build a review bundle from current tracked and untracked implementation bytes plus explicit evidence. Preserve support code needed to run the package and label earlier architecture accurately. Exclude runtime secrets, user databases, and protected development instructions as the bundler specifies.
- [ ] Update this plan's checkboxes only with concrete references to fresh evidence. Publish no full-product completion statement while any required journey is missing or relies on an unported legacy path.

## 4. Deferred web integration

The user has made technical mechanics the priority. Web can later consume the same whole-object and workflow operations. It remains an optional global module with one listener, `web`/`web stop`, bind/port settings, module-contributed pages, and the accepted optional token-link/session behavior. A terminal is its own optional module with declared platform support.

Future editor work must preserve authored text and rich bindings, expose complete namespace objects/owned joins, show exact readonly inserted text and historical provenance, and display collected graphs without invented edges. Live object/workflow updates must retain selection, view position, and unsaved edits. These are deferred deliverables: existing standalone live HTML does not demonstrate integrated JavaScript or backend updates. No empty placeholder menus are acceptance evidence.

## 5. Remaining decisions and safe progress

Latest explicit decisions above are settled even when earlier documents still call them open. The following narrower questions remain; preserve source and progress on the independent mechanisms while they are resolved.

| Question | Current evidence and bounded implementation path |
| --- | --- |
| Canonical schema/prose discrepancies | Prose says TARGET/target and includes DE/SE/NE/combined/subtypes; the nested schema uses `type="purpose"`, `data/function/operator` and omits some fields. Retain all supplied content and document source-field mapping. Do not invent a universal enum or discard an answer. |
| Shallow shape versus full Native account | Current Canonical shallow restrictions and older full actual-artifact accounts differ in placement/detail. Preserve the exact maintained workflow and actual artifact context as attributable contributions; do not erase either by silently normalizing the prompt. |
| Final XML and incremental intake | Both authored final XML and live object writes exist in the requirements. The shared run must distinguish collected partial writes from final completion. It can retain both without forcing one transport on every workflow. |
| Default visibility and explicit selectors | The implemented Layers service treats a general-graph flag as a browsing default; explicit workflow selection can include it while still observing masks. Focused tests verify that behavior. Separately authored workflow/step override precedence still needs a complete execution contract; keep flags and selectors distinct. |
| Multi-input generation visibility | Every actual input is retained. Define whether a mixed generation is displayed as separately attributable target contributions or one inseparable result; do not invent partial visibility by slicing prose. |
| Workflow control flow | Rich preservation and preparation using packaged `data/workflows/grammar.json` are implemented. Seven-source preparation/structure tests do not establish model interpretation quality. Preserve authored meaning and review unsupported grammar without treating XML tags as executable. |
| Historical nonce and onboarding rules | Current assignment nonce is eight hex characters; header includes assignment ID and step. Older workflow-revision nonce/24-hour/done rules need an explicit mapping to submit/complete/abort and durable run refs. Preserve existing behavior until changed deliberately; do not invent expiration. Map old harness-parent provisioning to the new optional adapter without assuming PID identity. |
| Artifact text threshold and migration | ArtifactHistory now defines 3 MB as 3,000,000 aggregate changed UTF-8 bytes: smaller changes are whole, larger text uses Python line edits, binaries stay whole. This is a documented engineering choice. Older history IDs still require a lossless migration mapping, not reinterpretation as new namespace IDs. |
| Export generation compatibility | Record the format/runtime versions needed for an archive to resume. Preserve unknown fields and report unavailable modules/resources; do not promise arbitrary plugin dependency discovery. |

## 6. Authoritative acceptance journeys

Each journey must run through the public CLI/shared services against the delivered package. A fixture proves deterministic mechanics; substantive provider work and source inspection establish what the agents actually received and returned.

| Journey | Actions | Required retained evidence |
| --- | --- | --- |
| A — removable chassis | Load showcase, alter a glued setting, enter/exit its menu and nonce; use both event modules; unload one while another works. | Contextual help before/during/after, exact settings retention, event refs, job/result, owned resource cleanup. |
| B — storage preservation | Put open joins in split stores, issue a ref, revise, export a subset, merge into unified/project placement, relocate. | Exact historical resolution, unchanged IDs/open fields, unrelated joins retained, conflict report for divergent same version. |
| C — authoring and provenance | Convert a rich imported workflow across all formats, edit authored text, issue three steps with output bindings, inspect the final answer. | Source/aliases/attributes intact; old revision bindings intact; exact prompts and actual inputs; no unused-layer false dependencies. |
| D — shared work identity | Start asynchronous work, end client, resume status elsewhere, submit via MCP/CLI with issued header, finalize. Repeat across concurrent projects. | One run progression, matching nonce/header/PID diagnostics, no cross-context leakage, marker cleanup, preserved response. |
| E — real intake | Run Native on a code artifact and a non-code artifact, then Latent on each complete Native account. | Source identity/access, complete Native transfer, Latent isolation, RE-owned encounter EFs, actual answers plus semantic review notes. |
| F — reusable layers | Generate object/join knowledge and memory; select through masks; reuse in another workflow; hide a source and change a revision separately. | Correct recurrence, property branch applicability, exact reused refs, hidden dependency behavior, distinct stale/history state. |
| G — port and alternatives | Clone, change scoped medium/port properties, rerun affected recipes, retain sibling artifact outputs, hide port context. | Preserved original/unaffected contributions, actual changed guidance, both variants reconstruct byte-for-byte, detached current port inference. |
| H — portable continuation | Export selected modules/project while work is pending; remove access to original root/checkout/service/Git; launch wheel, resume, reconstruct and re-export. | Wheel hash, imported closure/history, no ambient-source reads, same exact refs, completed chain, returned archive works. |

The product is technically complete for this scope when A–H have current evidence and remaining limitations are stated at their real boundary. Deferred web presentation does not block these CLI mechanics.

## 7. Source coverage

| Source | Requirements carried into this plan |
| --- | --- |
| `product/PRODUCT-SPECIFICATION.md`, sections 1–13 | Semantics, objects, intake, knowledge, workflows, chassis, navigation, agent access, data, distribution, demos, and evidence. |
| `product/DECISIONS-AND-CONFLICTS.md` | Settled latest user choices and remaining source discrepancies; superseded envelope/single-EF ambiguity is not reopened. |
| `Canonical_Intake.xml` | Encounter-specific EF; recursive RE/OP/provider structure; authored names, schema, and retained raw responses. |
| `namespace-join-implementation-plan.md` | Universal object, open joins, configurable stores, exact retained refs, workflow prompt/output provenance. |
| `global-data.md` and `data_folder.md` | Origin identities, retained alternatives, producing operation, import preservation, working-folder continuity, Python reconstruction. |
| `../docs/rulebook/element/{name,description}.md` | Recoverable proper names and separation of universal Description from artifact particulars. |
| `../docs/SPEC.md`, sections 9 and 12–15 | Inference amortization, nonce/contextual menus, help/onboarding, producer evidence, property-sensitive re-inference; older implementation choices need current adapters. |
| `../feature-briefs/native-metaform-variants-specification.md` | Clone scoped interpretations, detach affected reasoning, reissue original prompts, preserve base/unaffected work. |
| `../feature-briefs/shared-knowledge-service-and-portable-projects-specification.md`, sections 1, 6, 8, 10–11 | Service liveness, owner isolation, eligible relationship closure, exact historical dependencies, export consistency, offline continuation and preservation. Earlier graph backends and fixed record shapes are not restored. |
| `intake-graph-viewer-plan.md` | Collected-data fidelity, source-preserving workflow interpretation, and deferred live/editor requirements. |
| `../docs/plugin-api.md`, `../docs/chassis-verification.md`, current source/tests | Existing signatures and bounded implementation evidence; earlier counts are not full-product acceptance. |
