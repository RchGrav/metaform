# Shared Knowledge Service and Portable Projects Implementation Plan

> **For agentic workers:** Use the applicable `superpowers:subagent-driven-development` or `superpowers:executing-plans` guidance when implementation is requested. The user authorized implementation of the recommended design on 2026-09-08. The task outline records the implementation approach; executed verification is recorded at the end of this plan.

**Goal:** Give service-backed projects reusable global and project-owned knowledge, and export one project's related understanding into an independently executable portable copy.

**Architecture:** The implemented design uses a user-local HTTP knowledge service with explicit project IDs, an owner-partitioned SQLite operational store, and local client SQLite execution state. The same knowledge operations run portably over project/global JSON. Installed Ladybug data copies retain Cypher for development and analysis; core operation and export are independent of Cypher.

**Tech Stack:** Existing Python 3.11+, SQLite, JSON, filelock, CLI/registry, MCP, Flask workbench and Ladybug support. Use existing dependencies and Python standard-library HTTP facilities; no runtime dependency was added.

**Spec:** [Shared knowledge service and portable projects — specification](shared-knowledge-service-and-portable-projects-specification.md).

## Global constraints and status

- The [feature brief](shared-knowledge-service-and-portable-projects.md) establishes R1–R7; Rich's review clarification establishes R8, preserving installed Cypher while requiring portable core operation without it.
- The specification's §2 quotes the selected authoritative semantic equations. Preserve those source relationships and source contents; implementation implications do not amend them.
- The specification is the accepted enhancement document alongside canonical [docs/SPEC.md](../docs/SPEC.md). The recommended P1–P9 design was reviewed and accepted for implementation; alternatives remain documented for context.
- Python support remains `>=3.11`; the existing CI matrix is Python `3.11` and `3.13`.
- Portable knowledge is JSON; portable execution state is local SQLite. Core graph/prompt/workflow/export operations do not require Cypher.
- Connected mode retains installed analytical backend copies and Cypher; this is not a requirement that the portable runtime gain native query support.
- Returning portable changes to shared service knowledge is undeveloped scope. Existing archive history import behavior remains distinct.
- Preserve unrelated work and instruction/tooling files. Implementation is authorized; public push, release and deployment remain separate actions.

## Design decisions and sequencing

The plan follows P1–P9 exactly, including P2's central SQLite recommendation. P2 adds cross-owner crash atomicity and durable mutation receipts beyond the feature brief. The smaller P2-alt is viable: a sole-owner service can serialize existing backend calls and snapshot reads under one service lock, retaining present partial-write/retry behavior without a durable transaction coordinator. The user accepted the recommended P2 design before implementation. Choosing P2-alt changes task 2's storage implementation, task 5's recovery assertions, and task 6's snapshot mechanism; it need not change project selection, transport, reference ownership or the closure rule.

Other consequential decisions are summarized in spec §12: connected execution placement (task 4 onward), new-project default mode (task 4), attachment representation (tasks 6–7), historical evidence traversal (tasks 6–8), and custom module dependency declarations (tasks 7–8). Work on independent contracts, tests and documentation can proceed after design review without treating every open choice as an implementation blocker.

Dependencies: **1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10**. Task 9's analytical-copy work can run after task 3 in parallel with tasks 4–8 once interfaces are stable. UI work in task 4 and dependency fixtures in task 7 can also be separated with file ownership. Do not parallelize edits to shared `App`, graph interfaces, or portable exporter without coordinating ownership.

## Component map and interfaces

New components are intentionally limited to three runtime modules plus one registry module:

| Path | Responsibility |
| --- | --- |
| `src/metaform/knowledge.py` (new) | Operation contract, owner-bound graph adapter, central SQLite store and portable local dispatcher. Keeps HTTP out of graph semantics. |
| `src/metaform/service.py` (new) | Discovery/startup, authenticated HTTP dispatcher, service lifetime, installed analysis-copy refresh/query. |
| `src/metaform/knowledge_export.py` (new) | Pure owner-aware closure, typed dependency discovery and canonical snapshot digest. Used by service and portable runtime. |
| `src/metaform/modules/project.py` and `src/metaform/data/modules/project.json` (new) | Project registration/current/list/relocation command handlers and manifest. |
| Existing `app.py`, `graph.py`, `backends.py` | Mode/bootstrap and reusable graph record semantics. No HTTP-specific behavior in semantic normalization. |
| Existing `portable.py`, `history.py`, `continuation.py`, `locking.py` | Snapshot/state consistency, archive layout, filtered assets, relocation and continuation. |
| Existing `workflow.py`, `prompts.py`, `rulebook.py`, `schemas.py`, `intake.py` | Shared resolution boundary and atomic inference submission. Preserve authored operations. |
| Existing transport/viewer/module paths | CLI/MCP/project display and existing graph/native query routing. |

Contract names below describe the implemented interfaces. JSON-shaped types use ordinary dictionaries; do not introduce a type framework merely to implement them.

```python
# src/metaform/knowledge.py
Owner = str                         # "global" or "project:<uuid>"
Key = tuple[str, str, str]          # (owner, "element" | "join", id)

class KnowledgeStore:
    def __init__(self, path): ...
    def call(self, project_id, operation, arguments, request_id=None): ...

class LocalKnowledge:
    def __init__(self, project_id, project_graph, global_graph,
                 schemas, archive_dependencies=None): ...
    def call(self, operation, arguments, request_id=None): ...

class BoundGraph:
    def __init__(self, knowledge, owner): ...
    # Preserve existing signatures/return shapes for get, put, search, joins,
    # provenance, export, assemble, rename_elements, delete_joins, clean, stats,
    # similarity and merge_perspectives. No remote filesystem `path`.

# src/metaform/service.py
class RemoteKnowledge:
    def __init__(self, home, project_id): ...
    def call(self, operation, arguments, request_id=None): ...

def ensure_service(home, timeout=30): ...  # verified endpoint, not marker truth

# src/metaform/knowledge_export.py
# snapshot is a stable reader over one captured revision; exact read operations
# are those enumerated in spec §8, with owner-qualified keys.
def project_closure(snapshot, project_id, execution_roots): ...
def execution_dependencies(state): ...
def selected_digest(closure, normalized_runs): ...
```

The `...` bodies above denote interface signatures, not unspecified behavior: operation bodies/results are defined by spec §§6–9 and the tasks below. `call` returns the result object at the local adapter boundary; transport envelopes carry revision/service metadata separately. Snapshot results retain `revision` explicitly. Define a single error mapping for `unknown_project`, `service_unavailable`, `request_id_conflict`, `location_mismatch` and missing-record results; unresolved graph references remain result data as specified, not generic exceptions.

## Task 1 — Owner and reference contract with source-preservation fixtures

**Result:** A tested identity/reference model realizes R3/R4/R6/R8 and spec §§2,7–8 before transports or storage decisions obscure it.

**Files:** Create `tests/test_knowledge_contract.py` and the contract/adapter declarations in `src/metaform/knowledge.py`. Reuse `graph.join_participants`, `scoped_join_references`, `scoped_export`, `backends.normalized`, and `similarity.compare`. Extend existing `tests/test_graph_perspectives.py` only where a reusable existing fixture needs additional owner assertions.

**Consumes:** Existing graph export shape `{elements, joins, observations}`. **Produces:** Owner-qualified current keys, additive `participants[].owner` / `reference_owners`, precise reference resolution, and lossless source round-trip behavior.

- Add fixtures with project A/B/global each containing ID X, native/archaeology variants with different descriptions, and equal authored join IDs with different purposes. Assert owner and source are independent keys. Add endpoint plus participant cases where participants omit an endpoint, and an explicitly B-owned ref from A.
- Run `uv run --frozen pytest -q tests/test_knowledge_contract.py`; verify the new owner-resolution tests fail on missing contract behavior.
- Implement the spec §7 rules: project-author reference resolves within author owner then global; global author stays global; explicit owners stay precise; Element incidence can find eligible A/global joins at the same semantic address, while join-reference incidence compares qualified join identity. Keep semantic strings unchanged.
- Add the source round-trip assertions below using existing record fixtures, run them over SQLite/JSON/Ladybug inputs, and verify the outputs match:

```python
assert copied.get("X", scope="native") == original.get("X", scope="native")
assert copied.get("X", scope="archaeology") == original.get("X", scope="archaeology")
assert copied.export()["observations"] == original.export()["observations"]
assert {j["source_id"] for j in copied.joins()} == {
    j["source_id"] for j in original.joins()
}
```

- Update `docs/architecture.md`'s record/reference description when this contract is implemented. No semantic equation changes go into prompts or SPEC.

**Compatibility:** Legacy refs gain owner context from their store, not a string rewrite. Explicit import must preserve observation IDs/timestamps; SQLite `Graph.put(..., "imported")` currently creates an additional observation, so add a raw import path where exact transport/import is required, preserving ordinary authored-write behavior.

## Task 2 — Service-owned knowledge, registry and migration

**Prerequisite:** Task 1; P2 was selected. **Result:** Durable owner-scoped knowledge operations and non-destructive adoption (R1/R6, spec §§4,7,10).

**Files:** Implement `KnowledgeStore`/`BoundGraph` in `src/metaform/knowledge.py`; narrowly extract reusable SQL/normalization from `graph.py`/`backends.py`; create `tests/test_knowledge_store.py`. Use existing `App` path/config helpers without starting App during raw migration.

**Consumes:** Spec §6 operations and task 1 reference/source contract. **Produces:** `KnowledgeStore.call(project_id, operation, arguments, request_id)` and registry entries; owner-partitioned schema exactly as spec §7.

- Write tests for project registration idempotency by canonical path, two owners with equal IDs, scoped search returning both owner variants, raw import preserving source records, and a failed adoption leaving the existing project readable.
- Run `uv run --frozen pytest -q tests/test_knowledge_store.py`; observe the new behavior missing.
- Create `projects`, owner-qualified Elements/joins/participants/observations, schemas, receipt and revision tables. Wrap a mutation and its result receipt in one transaction. Key receipts by `(project_context, request_id)` and hash project context, operation and arguments; equal local request IDs in A/B must retain independent results. Reuse normalizers without instantiating an App or reseeding on each service request. Replace ID-only joins/observation foreign keys with owner-qualified keys inside this store.
- Implement project/global `graph.*` methods, `schema.get/put`, and registry operations. Preserve an explicit owner on every query. Test invalid project IDs and attempts to write B through A's envelope. Treat similarity as structural source records; current source edits leave the other source intact.
- Implement legacy export/import by configured backend. Import the home global corpus once per source home/digest, preserve originals, and publish the project service marker only after successful source/count verification. Report competing pre-existing record content for an explicit migration resolution; do not make up global enrichment semantics.
- Run `uv run --frozen pytest -q tests/test_knowledge_store.py tests/test_graph_perspectives.py tests/test_graph_similarity.py`; expect all pass, including raw preservation across existing backend formats.
- Update `docs/architecture.md` and `docs/next-version.md` storage/migration sections with the implemented storage choice and legacy path behavior.

**Compatibility:** Do not migrate every directory on ordinary startup. Existing legacy graph files remain intact. Optional Ladybug copies are handled separately in task 9, not removed by this task.

## Task 3 — Verifiable service lifecycle and transport

**Prerequisite:** Task 2. **Result:** Service-backed loading actually verifies, starts and reuses one live owner (R2; spec §6).

**Files:** Create `src/metaform/service.py` and `tests/test_service_lifecycle.py`; reuse `locking.py`'s FileLock practice and `util.python_environment`/atomic JSON helpers. Do not copy viewer marker-based liveness.

**Consumes:** `KnowledgeStore.call` and spec §6 envelope. **Produces:** `ensure_service(home, timeout=30)`, `RemoteKnowledge.call`, detached `python -m metaform.service --home`, health/status/stop operations.

- Write subprocess tests using temporary home/project directories inside each pytest temporary directory: first startup, verified reuse, stale endpoint/PID/lock files, eight competing starters, wrong-product HTTP listener, wrong challenge/credential, starter death before/after child readiness, child death during initialization, and a live owner that never becomes ready. Assert outcomes A1/A2, including bounded failure and no signaling of a recorded PID.
- Run `uv run --frozen pytest -q tests/test_service_lifecycle.py`; expected startup tests fail until the new service exists.
- Implement `start.lock`, child-held `instance.lock`, user-local token, loopback binding, fresh health challenge, atomic endpoint publication, and separate service log exactly as spec §6. Child lock acquisition is authoritative for storage ownership; only a correct ready health reply establishes liveness.
- Implement authenticated `/v1/operations`, explicit project envelopes and protocol/error mapping. Cache no active project in the service. Implement retry with the same request ID/body and persisted receipts; conflicting bodies must not execute twice. Add a test that drops the connection after commit and receives the original project-scoped result on retry; send the same local request ID from B with different arguments and assert independent execution/results.
- Implement graceful stop by verified endpoint request; drain accepted mutations. Ensure logs/startup progress do not enter MCP stdout. Retain service beyond client disconnect.
- Run `uv run --frozen pytest -q tests/test_service_lifecycle.py tests/test_knowledge_store.py`; verify spawned test processes are cleaned up by their owned process handles/authenticated stop.
- Update `docs/architecture.md` service lifetime and README troubleshooting with actual status/log commands once implemented.

**Compatibility:** Existing viewer/gateway remain separate processes with their current roles. The new knowledge service is not an MCP replacement or a model executor.

## Task 4 — Project context across App, CLI, MCP and workbench

**Prerequisite:** Task 3 and P3/P4/P4a decisions. **Result:** Each client and in-flight operation keeps the correct project and mode (R1/R7, A3/A13).

**Files:** `src/metaform/app.py`, `cli.py`, `mcp_server.py`, `portable_mcp.py`, `continuation.py`, `actor.py`, `viewer.py`, `modules/viewer.py`, `static/workbench.js`, `templates/index.html`; create `modules/project.py` and `data/modules/project.json`; tests `tests/test_project_context.py`, existing `test_mcp.py`, `test_viewer_scope.py`, `test_module_scope.py`.

**Consumes:** Verified `RemoteKnowledge`, `LocalKnowledge`, `BoundGraph`, registry entries. **Produces:** `app.knowledge`, mode-aware `app.graph/global_graph`, CLI/MCP project commands, project-specific workbench contexts.

- Add tests for the spec §5 precedence: binding, explicit selector, environment, directory; continuation conflicts; simultaneous A/B MCP requests with matching fixture run IDs; and two viewer tabs. Also assert portable marker chooses local mode before any service probe or packaged global seed.
- Run `uv run --frozen pytest -q tests/test_project_context.py`; expect new selection/bootstrap tests to fail.
- Separate location/binding/config resolution from App storage/seed initialization. New installed service-mode projects register once; legacy directories stay direct until `project connect`; portable mode initializes `LocalKnowledge`. Keep `App.db_path` project-local under P3.
- Parse early `--project` before App construction, covering normal CLI, `begin`, gateway and actor paths. Add `project connect/list/current/relocate`, `project.select` for MCP session context, and `service status/stop` registry commands. Avoid recursively bootstrapping the service within its own process.
- Bind immutable App context at request dispatch. MCP selection swaps only subsequent session context. Workbench project navigation uses project-specific URLs and shows project/path/mode separately from assignment/run. Keep existing source and similarity views.
- Run `uv run --frozen pytest -q tests/test_project_context.py tests/test_mcp.py tests/test_viewer_scope.py tests/test_module_scope.py`; manually inspect project selection/source views in two tabs with A/B records. Verify the displayed project matches requests and pending work.
- Update `README.md`, `docs/next-version.md` Start/Handoff/Storage and `docs/architecture.md`; keep model-facing semantic prompts unchanged. Runtime onboarding describes project selection only at the interface.

**Compatibility:** New UUID is not the history hash. Copy/move identity is handled explicitly by connect-new/relocate, and no project switch mutates another session's pending workflow binding.

## Task 5 — Preserve intake completion and recovery through the service

**Prerequisite:** Task 4. **Result:** Existing focal inference semantics survive transport, with the additional P2 atomic recovery guarantee clearly tested (R1/R6/R7, A11).

**Files:** `src/metaform/intake.py`, `knowledge.py`; tests `tests/test_service_intake.py`, existing `test_intake_pipeline.py`, `test_intake_handoff.py`, `test_intake_driver.py`.

**Consumes:** Current `Intake._owned`, `_contribution`, `_remember`, `_commit_inference`, `_finish`, `inference`; service transaction/receipt contract. **Produces:** `inference.contribute/commit/read` operations and portable equivalents.

- Add tests with two projects completing the same focal Type concurrently. Inject response loss after transaction commit and failure before commit; assert one global completion, project Latent records available, identical retry receipts, and no inference-complete marker from mere Type presence.
- Run `uv run --frozen pytest -q tests/test_service_intake.py`; ensure service-level completion tests expose the missing boundary.
- Replace client `_global_lock` use around multi-call writes with `inference.contribute` or `inference.commit`. Send the accumulated per-request focal snapshot already maintained by `_remember`; derive stable operation request IDs from project/run/assignment/operation. Keep prepared Latent inputs and existing global-definition preservation rules.
- Implement the entire spec §6 completion transaction in `KnowledgeStore`; return a durable receipt before local run-state advancement. On retry after local save failure, consume that receipt and complete the local transition. Implement the same logical operation in the portable dispatcher using existing local locks, without claiming multi-file crash atomicity there.
- Keep `inference.read` source completion/snapshot semantics and allow captured archive dependencies (task 6) to resolve missing current records. Preserve `inference_type`, `authored_id`, `source_id`, completion observations and separate Contextual/Latent views.
- Run `uv run --frozen pytest -q tests/test_service_intake.py tests/test_intake_pipeline.py tests/test_intake_handoff.py tests/test_intake_driver.py`; verify existing prepared input tests remain unchanged in intent.
- Update `docs/workflows.md` completion/reuse behavior and `docs/architecture.md` transaction/retry explanation. No authored inference rule changes are required.

**Compatibility:** Under P2-alt retain the existing locked sequence and partial-write/retry behavior instead of asserting central transaction rollback; document that selected alternative accurately.

## Task 6 — Owner-aware closure and consistent knowledge snapshot

**Prerequisite:** Tasks 1/2/5 and P7/P7b decisions. **Result:** Complete project-focused closure, including reified joins and focal snapshot dependencies (R3/R4/R6; A4–A7/A9/A10/A12).

**Files:** Create `src/metaform/knowledge_export.py`, `tests/test_knowledge_export.py`; extend `knowledge.py` snapshot/read support; reuse `graph.assemble`'s traversal concepts, not its one-store limitation.

**Consumes:** Stable snapshot reader `record`, `resolve`, `incident_element`, `incident_join`, `source_observations`, `dependencies` defined in spec §8. **Produces:** `project_closure(snapshot, project_id, execution_roots)` → `{revision, project, global, archive_dependencies, similarity, schemas, runtime_assets, unresolved}`. Project/global retain existing graph export shapes; dependency entries carry owner, kind, ID, provenance and stored body.

- Build A/B/global fixtures with A's W→X, global X→Y, global archaeology Y→Z, A archaeology Z→L, B X→Q; add g3/g4 reified cyclic joins with all endpoint/participant forms and one missing reference. Add equal join strings in A/global and explicit B refs. Remove X’s Element body while retaining eligible X→Y and assert Y is still reached while X is reported missing.
- Run `uv run --frozen pytest -q tests/test_knowledge_export.py`; expect missing closure behavior to fail. Use assertions equivalent to:

```python
result = project_closure(snapshot, "A", execution_roots=[])
assert {"X", "Y", "Z"} <= set(result["global"]["elements"])
assert "Q" not in result["global"]["elements"]
assert all(j["id"] != "b1" for j in result["project"]["joins"])
assert len({j["id"] for j in result["global"]["joins"]}) == len(
    result["global"]["joins"]
)
```

- Implement spec §8 pseudocode exactly: every current local source record is a root, eligible owner checks occur on every incidence/resolution, traverse both endpoints and all participants, visit owner/kind/ID and expand each Element address once. Resolve absent bodies to logical keys and discover incident joins before reporting missing bodies; never stop discovery merely because an Element row is absent. Retain whole relationship bodies. Scope/category/depth arguments never narrow export.
- Preserve all selected source observations. Keep historical snapshots exact. Latest reached focal completion Element IDs and join member refs seed current closure: a latest snapshot member Y with current global Y→Z must export Z even if the snapshot join is absent from current top-level joins. Older evidence follows only typed dependency closure separately. `inference.read` retains exact snapshot joins and resolves Element bodies current-global first, then captured snapshot Elements, then archive dependency bodies; use identical precedence in both modes. Never replace current records with historical contents. Similarity does not expand semantic closure; exclude a stored similarity join before calling `incident_join` on its identity, then compare retained independent project source graphs. Add an assertion that a semantic join reachable only by referencing that similarity join, and its otherwise unrelated target, are absent from the closure. Keep the missing ordinary Element X→Y assertion passing.
- Implement SQLite owner/reference indexes and single-read-transaction snapshot traversal. JSON creates one in-memory index over its captured two files under local locks and runs the same closure. Do not use Cypher, native graph procedures, namespace ancestry, or arbitrary prose matching.
- Test a 1,100-join cycle/chain, an n-ary missing member, unrelated global additions, provenance-only edits, and a writer committing halfway through snapshot traversal. Assert termination, unchanged unrelated extent, retained provenance and one coherent revision. Compare outputs between service SQLite and portable JSON.
- Run `uv run --frozen pytest -q tests/test_knowledge_export.py tests/test_graph_similarity.py tests/test_graph_perspectives.py`; expect exact owner/source/dependency equality after canonical ordering.
- Update `docs/architecture.md` traversal/snapshot explanation at completion. Update SPEC's accepted capability text only after Rich accepts a product-contract change; do not move this proposal into canonical semantics merely because implementation passes tests.

## Task 7 — Executable dependencies and a common resolution boundary

**Prerequisite:** Task 6 and P7a/P7c decisions. **Result:** Prompts/workflows receive usable related meaning and executable dependencies in both modes (R4/R7, A4/A8/A12).

**Files:** `src/metaform/knowledge_export.py`, `workflow.py`, `prompts.py`, `rulebook.py`, `schemas.py`, `registry.py`, `modules/graph.py`, `modules/workflow.py`, `data/schemas.json`; create `tests/test_knowledge_dependencies.py`. Preserve existing module manifests except the precise optional portable metadata additions needed by built-ins.

**Consumes:** `execution_dependencies(state)` and `knowledge.assemble`; existing prompt snapshots and workflow graph projections. **Produces:** Typed graph/schema/asset dependencies and installed/portable caller parity.

- Write one fixture with a local workflow attached to global X, `call` child workflow, `parallel` string/dict/embedded branches, referenced prompt, semantic rule codes, condition rule, response schema with nested `$ref`, and a `file:` prompt whose saved `base_dir` is outside project contents. Put an unrelated ID-shaped string in an answer; it must not become an export root.
- Run `uv run --frozen pytest -q tests/test_knowledge_dependencies.py`; confirm missing field traversal fails.
- Materialize proposed workflow/step attachments as ordinary `workflow_attachment` joins at import. Extract `step.workflow`, `branches` forms, `prompt_ref`, `rule_codes`, schema refs, `stack[].definition`, pending/assignment prepared snapshots and resolved focal values exactly from current Engine data. Preserve unknown literal content; do not guess references from all strings.
- Capture file prompt bytes for future unissued steps as well as issued work, including external saved base directories. Materialize assets under `resources/workflows/<workflow-revision>/`, resolve executable `file:` refs through a captured resource mapping, retaining original authored definitions, locations, stack frames and prepared text revisions, and report known missing resources explicitly. Resolve semantic rule codes to existing `rule:<code>` records; recursively bundle registered schemas while retaining exact schema bodies. Keep authored prompt text and control flow unchanged.
- Define custom manifest `portable.files` and `portable.knowledge_refs` as spec §8 proposes. Include project module assets and only referenced/selected shared modules plus declared dependencies. Known missing declared assets produce an explicit runtime-dependency result. Arbitrary undeclared handler dependencies are not automatically discovered.
- Route cross-owner assembly through `app.knowledge` in `prompts.prepare`, `Engine.next`, graph browse and relevant workflow module callers. Keep exact per-owner get/dump views; composed search returns independently addressable owner/source variants instead of overwriting them by bare ID. Keep Latent assignment retrieval global-only as currently intended.
- Run `uv run --frozen pytest -q tests/test_knowledge_dependencies.py tests/test_execution.py tests/test_module_scope.py tests/test_mcp.py`; compare prepared text, rule revisions, condition/control-flow outcomes and source graphs across service and JSON adapters.
- Update `docs/workflows.md` attachment/dependency representation, `docs/architecture.md` resolution boundary, and `docs/next-version.md` prompt/module behavior when shipped.

## Task 8 — Project-focused archive, digest and offline continuity

**Prerequisite:** Tasks 6–7. **Result:** Independent portable operation and continued-work export without unrelated shared artifacts (R3–R7, A8–A13).

**Files:** `src/metaform/portable.py`, `history.py`, `continuation.py`, `workfolders.py`, `locking.py`, `app.py`, `schemas.py`, `registry.py`, `packaging.py`; tests `tests/test_portable_knowledge.py`, existing `tests/test_next_version.py`; extend `tools/check_distribution.py` in task 10 after focused tests pass.

**Consumes:** Closure snapshot/dependency manifest, selected state rows and `selected_digest`. **Produces:** `metaform-export/2`, import support for `/1` and `/2`, source-preserving portable JSON and local SQLite, digest version 2.

- Write the combined fixture: A/B share X; B has local X→Q, distinct pending nonce/workfolder baseline/module; package data/global contains unrelated U; A's latest focal completion references D absent from current top-level joins, while current global D→E exists; E must travel. A future workflow step uses `file:` under an external saved `base_dir`. A has a running nested workflow with multiple assignments and retained file work. Assert no B/U payload anywhere in graph JSON, assignments, baselines, module assets or embedded seed files.
- Run `uv run --frozen pytest -q tests/test_portable_knowledge.py`; verify current whole-home/whole-global copying fails the new fixture.
- Add a project snapshot lock at the outer short state/workfolder transition boundary, always before current run locks; audit direct `App.db()` mutation callers. Reuse a shared per-project reentrant acquisition context for nested same-project writes, including across App instances in the process, rather than calling existing `locking.lock` to construct an independent FileLock at every level. `run_locked` → `Engine.next` → `App.save_run` must nest without self-blocking; direct mutations outside a transition use that same context. Test nested next/save_run together with an export in another process, asserting successful completion and a coherent before-or-after snapshot. Capture SQLite rows, closure, selected assets and their file hashes into temporary staging, release locks, then compress. Keep model execution outside locks. Changed source bytes during capture produce the explicit changed-path outcome from spec §8.
- Make history checkpoint and archive serialization consume the same captured closure/digest. Digest source observations, completion evidence and selected dependency/schema data, not unrelated globals or service revision. Preserve historical digest versions. Store selected global snapshot for new checkpoints; do not rewrite old history.
- Replace whole-home assignment/baseline/module copying with selected run/request/project/workfolder membership. Audit `assignment_home` overrides and mirrored continuation indexes; preserve only records associated with retained A jobs. Filter or replace package global seed/schema indexes in the archive. Test first import, second startup and re-export to expose reseeding leaks.
- Write portable config before App construction. Restore raw graph/source records, JSON backend and local execution SQLite. Relocate every `pending`, `assignments` entry, `stack` frame, workfolder row, assignment file and workfolder marker with one schema-aware relocation routine. Clear ephemeral process/gateway/viewer execution markers; keep durable answers, receipts, pending work and exact snapshots.
- In an empty Python environment with no originating service/home and no Git, run exported graph get/put, prompt preparation, `begin`, answer/next through a nested workflow, viewer/source reading, and re-export. Reopen the continued archive and verify the next pending assignment and changed source record. Explicit Cypher request reports capability absence; no core command attempts to use it.
- Test v1 import, v2 inclusive replacement, divergent sibling history, and provenance-only edits triggering changed knowledge digest. Run `uv run --frozen pytest -q tests/test_portable_knowledge.py tests/test_next_version.py tests/test_execution.py`.
- Update `README.md` portability, `docs/next-version.md` Versions/exports and Handoff/continuity, `docs/workflows.md` offline dependency behavior, and `docs/current-work.md` with evidence actually obtained. State optional external-model/schema-validation/native capabilities accurately.

**Compatibility:** Archive import remains portable working-copy/history behavior. No step returns portable edits to the shared service or repurposes Git sync as reconciliation.

## Task 9 — Preserve installed Cypher over an explicit data copy

**Prerequisite:** Tasks 2–3; independent of portable implementation after those interfaces stabilize. **Result:** Rich's R8 correction is realized: useful native analysis remains available, while the operating model works without it (A14).

**Files:** `src/metaform/service.py`, `knowledge.py`, `modules/graph.py`, `data/modules/graph.json`, existing `backends.py:LadybugGraph`; create `tests/test_service_analysis.py`.

**Consumes:** Coherent owner-specific `graph.export` snapshot/revision and existing `LadybugGraph.put/query`. **Produces:** `analysis.refresh` and `analysis.query` service operations, selected-backend status and revision-labelled Cypher results.

- Add tests hydrating A/global copies, querying known records/provenance, changing central knowledge without refreshing, refreshing again, and running every core/export fixture with Ladybug unavailable. Assert old/new `source_revision` is observable and no partial copy is queried.
- Run `uv run --frozen pytest -q tests/test_service_analysis.py`; verify service copy routing is missing.
- Implement `analysis.refresh({owner, backend: "ladybug"})`: read the selected authoritative owner under one read snapshot (a full owner copy for analysis, separate from project-focused portable closure), hydrate a temporary Ladybug copy using raw source import, write owner/source-revision/refreshed-at metadata, then publish under the per-copy lock. The global analytical copy may contain all global records; it is not an export root or archive asset.
- Implement `analysis.query({owner, query, parameters})` against the selected copy and return `{source_revision, refreshed_at, result}`. Keep query effects within the disposable analytical copy. Repeating `graph backend --name ladybug` explicitly regenerates it from authoritative data; this is snapshot refresh, not bidirectional synchronization or portable reimport.
- Route connected `graph backend` and `graph cypher` through those operations; preserve legacy installed backend behavior. Portable mode uses its existing unavailable-capability response for explicit Cypher and otherwise ignores the native copy.
- Run `uv run --frozen pytest -q tests/test_service_analysis.py tests/test_knowledge_export.py tests/test_portable_knowledge.py`; prove both installed analysis and portable-independent operation.
- Update `docs/architecture.md` and `docs/next-version.md` to explain operational storage versus analytical copy, explicit refresh and visible revision. Do not describe Cypher as lost or as necessary for core Metaform behavior.

## Task 10 — Integration evidence, maintained docs and delivery review

**Prerequisite:** Tasks 1–9; accepted design choices reflected consistently in both artifacts. **Result:** Feature acceptance and release-shaped validation with accurate evidence, not a claim inferred from code existence.

**Files:** `.github/workflows/wheel.yml` only if required to exercise new coverage; `tools/check_distribution.py`; maintained `docs/architecture.md`, `docs/next-version.md`, `docs/workflows.md`, `docs/current-work.md`, `README.md`, and accepted capability additions in `docs/SPEC.md` where warranted. Do not modify protected instruction/tooling files.

- Extend `tools/check_distribution.py`'s `check_offline` to execute A8/A9's selected closure/continuation fixture, verify absence of service/backend access, and re-export. Extend installed-wheel checks with first start/reuse and optional analysis-copy behavior.
- Run focused feature suites once after the final related changes and review all A1–A14 outcomes. Review both modes through ordinary CLI, early `begin`, actor/gateway and MCP entry paths. Check no project/session mismatch in workbench/API requests.
- Run the repository's current full checks, matching `.github/workflows/wheel.yml` on Python 3.11 and 3.13:

```bash
uv sync --frozen
uv run --frozen pytest -q
uv run --frozen python tools/build_distribution.py
uv venv /tmp/metaform-feature-wheel-check
uv pip install --python /tmp/metaform-feature-wheel-check/bin/python dist/*.whl
/tmp/metaform-feature-wheel-check/bin/python tools/check_distribution.py
```

Use a fresh task-specific environment path if that path already contains unrelated work. Read all outputs. Fix failures in scope and rerun only affected checks before final comprehensive verification. These commands are commissioned for implemented work; they were not executed to certify this proposal.

- Check maintained docs against the final behavior: service ownership/lifetime, registration/selecting project versus assignment, independent source graph views, global extent and historical dependencies, portable limits, Cypher copy/refresh, and the explicit absence of a reconciliation feature.
- Review scoped diff and test evidence; stage only implementation files within agreed scope. Follow the user's local review workflow; no public push/release/deploy is implied. Record actual revision, changed paths, executed commands/results and unresolved limitations in the implementation review handoff.

## Specification coverage and review handoff

**Artifact paths:**

- `/home/rich/metaform/feature-briefs/shared-knowledge-service-and-portable-projects-specification.md`
- `/home/rich/metaform/feature-briefs/shared-knowledge-service-and-portable-projects-implementation-plan.md`

**Feature goal:** Shared global inference and project-owned knowledge, with a project-focused portable copy that continues independently. **Semantic contract:** canonical `docs/SPEC.md` and the exact selected equations in specification §2; ownership and storage cannot reconcile or collapse Contextual/Latent source contents. Rich's Cypher clarification is authoritative: preserve installed analysis capability and core portable independence together.

**Planning baseline:** `86b893ecf6813ffea3d5eaa5af60a3d34d8b81c3`, branch `main`; live origin/main matched on 2026-09-08. Relevant local differences are the modified `AGENTS.md` and untracked user/runtime/generated artifacts listed in specification §3. This describes the original planning inspection; implementation evidence follows below. Instruction files remain untouched by this work.

**Implemented realization:** explicit per-request UUID project context; actual authenticated liveness/startup; central operational SQLite plus optional installed Ladybug analysis copies; local connected execution state; same knowledge interface over portable JSON; incident global/A-local closure with qualified reified references; typed executable and historical dependency capture; selected snapshot/digest and owner-filtered archive assets. P2's extra atomicity is an accepted design choice. P2-alt remains a documented alternative.

**Accepted choices:** The recommended P1–P9 design in specification §12, including central SQLite (P2). Shared Type semantic enrichment and portable-to-service reconciliation remain outside developed scope. Review must distinguish an accepted requirement from the proposed mechanism used to realize it.

| Requirements/scenarios | Implementing tasks |
| --- | --- |
| R1; A3/A13 project ownership and migration | 1,2,4,5 |
| R2; A1/A2 verified lifecycle | 3,4 |
| R3/R4; A4–A6/A9/A12 closure and dependencies | 1,6,7,8 |
| R5; A8 offline runtime | 4,7,8,10 |
| R6; A7 independent sources | 1,2,5,6,8 |
| R7; A3/A4/A8 workflow/prompt parity | 4,5,7,8 |
| R8; A14 optional native analysis/core portability | 6,8,9,10 |
| A10/A11 snapshot and proposed atomic recovery | 2,5,6,8 |

**Review request:** Assess fitness for the feature, semantic consistency, coherence across storage/CLI/MCP/workflow/portable processes, traversal completeness and ownership checks at every hop, source/observation/focal-snapshot preservation, actual service liveness, copy refresh visibility and Cypher-independent core operation. Check whether the plan implements every specification requirement and whether added guarantees or schema changes justify their cost relative to existing mechanisms. Use the paths/symbols in specification §3 and each task to verify implementation claims.

This handoff is part of the requested implementation plan, not a separately generated agent prompt. It introduces no runtime inference instructions.

## Evidence from this specification task

Executed by the specification writer: inspected the supplied agent prompt, applicable project instructions, feature brief, canonical semantic sources, current architecture and implementation paths; refreshed HEAD/branch/remote and queried live origin/main; saved/read back both requested artifacts; checked local Markdown references and key symbols, requirement/scenario/task coverage, whitespace and scoped diff; staged only the two artifacts. Final staging/reference-check results are reported to the coordinator after those checks execute.

The coordinating reviewer separately reported **31 passing baseline tests** from `tests/test_next_version.py`, `tests/test_graph_perspectives.py`, and `tests/test_module_scope.py`. These establish current baseline behavior, not the proposed service or traversal. No new runtime tests, full suite, wheel build or installed/portable feature acceptance are claimed complete by this planning work. Historical suite results in `docs/current-work.md` and `docs/verification.md` remain historical.

## Implementation delivery — 2026-09-08

Tasks 1–10 are implemented against baseline `86b893e`; the changes are local and
have not been committed or pushed. The component map above identifies the runtime
boundaries; supporting tests, distribution tools and maintained documentation
were updated within this feature's scope. No semantic source equation or authored
expert prompt was changed.

- Full `python -m pytest -q`: **396 passed** on Python 3.11.6 and **396 passed** on
  Python 3.13.5 after final repairs.
- `python tools/build_distribution.py`: wheel and standalone archive built.
  Fresh installed-wheel environments on both Python versions passed
  `python tools/check_distribution.py`, including installed Cypher and service-free
  nested continuation/re-export from an empty Python environment.
- Chromium: independent project tabs and selection, correct project/mode display,
  analysis-copy refresh, no JavaScript errors.
- Independent reviews covered the storage, transport, intake, dependency,
  project-context and portable boundaries. Confirmed findings were repaired and
  rechecked, including repeated invocation of same-origin sibling archives.

The task steps above describe the implementation and intended verification
approach, not a claim that every suggested command or fixture grouping was run
literally. Executed evidence and its limits are consolidated in
[verification](../docs/verification.md). Ordinary central mutations still
reconstruct one owner partition; arbitrary undeclared module dependencies and
portable-to-service reconciliation remain outside implemented capability.
