# Shared knowledge service and portable projects — specification

Status: recommended design accepted for implementation on 2026-09-08. This document develops the [agreed feature brief](shared-knowledge-service-and-portable-projects.md) while preserving the canonical [semantic contract](../docs/SPEC.md). The accompanying [implementation plan](shared-knowledge-service-and-portable-projects-implementation-plan.md) tracks delivery. R labels identify established requirements; P labels retain the design choices and their considered alternatives. The recommended central SQLite design is the implementation target.

## 1. Purpose and established requirements

People and agents working across projects use centrally maintained inference, then export one project's developed understanding into an independently usable copy. The service and portable runtime expose the same project, graph, prompt, and workflow operations.

| ID | Established requirement |
| --- | --- |
| R1 | The shared service stores global inference and each project's local data, tracks projects, and supplies their associated knowledge. |
| R2 | Service-backed CLI and MCP startup verifies actual service liveness, reuses a verified instance, and starts one when needed. PID files, locks, and markers alone do not establish liveness. |
| R3 | Export gathers the selected project's local inference and related global inference through globally inferred joins and joins inferred locally for that project. |
| R4 | Workflow attachments and latent inference can reach objects outside the project's original contents; their eligible relationships participate in export. Another project's local joins do not extend the selected project's traversal. |
| R5 | Portable operation uses JSON knowledge storage and local SQLite execution state and continues independently of the service and its database. |
| R6 | Source provenance and the complete, independent Contextual and Latent representations survive storage, retrieval, modification, and export. |
| R7 | Prompts, workflows, and graph operations retain the same operating model in both modes. |
| R8 | User clarification during review: core operations must run from the exported form without Cypher; installed backend copies retain Cypher where useful for system development and analysis. |

The owner clarified the capability relationship during this specification review:

> cypher support is still supported ijn the back end since it has a copy of the data there.. the system has to be capable of running from its exported form which will not have that support available and if you design around it as a requirement you are actually breaking the system capabilities.. if the system operates without it properly, those capabilities can be kept whewre they are valuable in system development and analysis

Returning portable changes to the shared service remains undeveloped scope. Existing archive import is described in §10 without implying reconciliation. This feature does not settle existing open semantic questions about global Type enrichment or alias/address implementation. Local OP contents describe the actual project and its receiving purposes; that meaning is settled.

## 2. Authority and semantic equations

The [semantic equation reuse rule](../docs/semantics/semantic_equation_reuse_rule.md) says:

> Treat every authoritative semantic statement, definition, rule, constraint, and example as a semantic equation.

> A semantic equation may be referenced, selected, combined, ordered, applied, instantiated, or quoted when constructing prompts and performing inference. Its wording does not need to appear in every generated prompt unless the prompt requires the equation explicitly; however, any use of the equation must preserve the semantic relationship expressed by the source.

The following selected source wording remains authoritative; implementation implications in the rest of this document do not replace it.

Historical wording from [SPEC, semantic contract §1](../docs/SPEC.md#1-type-identity); the exact equation remains Type identity, not a requirement for generic artifact descriptions:

> For an Artifact Type `T`, the formal identity is the exact set:
>
> `C(T) = {(rᵢ ∧ pᵢ ∧ e)}`
>
> where each conjunction binds:
>
> - `rᵢ` — Receiving Entity: the **who or what** receiving the effect;
> - `pᵢ` — Operative Purpose: the **why** owned by that Receiving Entity;
> - `e` — the Type's single Encounter Function: the **how** through which the effect is realized or encountered.

> These definitions describe the semantic relationship that protects type meaning through change. They do not prescribe a runtime identity-checking mechanism.

From SPEC §6:

> Project-local linked properties remain project-local. Their presence does not automatically promote them to global type knowledge.

Current intake semantics are recorded in `docs/semantics/artifacts-and-functional-intake.md` and `docs/SPEC.md`. Types classify and organize the Namespace; Native descriptions capture the actual artifacts, their functionality, and their specific receiving OPs. Intake starts with the exterior receiver's OP, identifies the Defining Element whose EF summarizes the artifact's combined result, and recursively follows actual requirements and properties. The Native Metaform is the project's Inference Metaform. Latent inference is callable on everything Native built, including descriptions, joins, and OPs, while remaining blind to repository implementation details. Global reuse is separate from primary intake. Native and latent provenance remain distinct; this correction does not choose a full graph or delta output or change structural comparison.

Exterior means not part of the project. External means external to the functionality being examined but still in the repository. Control or ownership does not define exterior; exterior entities can provide or receive. Material can include photos, contracts, stories, resale assets, or several projects. Context establishes whether media is an asset or standalone artifact. A Supportive Element contributes to the subject or purpose; mere co-presence in a scene does not establish that contribution.

Parametric is a Type's tunables array: its entries are acknowledged and reserved against Namespace Elements, and adjustment alone does not constitute acceptance. Notable is retired as a separate rubric; the relevant OP already makes the Element's participation explicit.

Existing source comparison retains independently observable contents and provenance. Its shape-similarity layer records structural correspondence without copied semantic payload.

Shape membership, exactly as defined there:

- `01` — structure present in the Contextual Metaform only
- `10` — structure present in the Latent Metaform only
- `11` — the same nodes and join structure are present in both

> These values do not encode confidence, correctness, precedence, or semantic reconciliation. When both source graphs contain the same nodes and a join between them, the similarity layer may represent that structural agreement as `11`. If the source join contents differ, both source joins remain intact in their respective graphs and retain their own provenance; the similarity layer does not collapse, copy, or reconcile their contents.

From SPEC §9:

> The Metaform stores reusable semantic understanding, not a catalog of completed task answers. The prompt/workflow and Metaform remain separable: a prompt describes an operation; the Metaform supplies previously inferred project/type meaning through which that operation is interpreted.

[SPEC §§5–7](../docs/SPEC.md), [functional typology](../docs/semantics/functional_typology.md), [inference rules](../docs/semantics/inference_metaform_rules.md), and [aliases](../src/metaform/data/semantics/aliases.md) remain the sources for namespace meaning, valid prefixes, and Encounter propagation. This proposal transports their existing records and source text; it creates no new semantic equation, namespace grammar, inference gate, or model-facing instruction. Historical glossary language about merging graphs does not supersede SPEC §8. [Current work](../docs/current-work.md) and [discussion handoff](../docs/discussion-handoff.md) distinguish completed corrections from exploratory proposals.

## 3. Inspected baseline and current process

Inspected checkout: `/home/rich/metaform`, branch `main`, HEAD `86b893ecf6813ffea3d5eaa5af60a3d34d8b81c3`. A read-only `git ls-remote origin refs/heads/main` on 2026-09-08 returned the same revision. No source update was needed. The configured repository is `RchGrav/metaform`; existing authenticated access is reused. Local differences were modified `AGENTS.md` and untracked `.test-tmp/`, `AGENTS.bak`, Zone.Identifier sidecars, `prompts/.README.md.kate-swp`, and generated prompt files. These are preserved. This work writes and stages only the two requested design artifacts.

| Current evidence | Consequence for this feature |
| --- | --- |
| [App](../src/metaform/app.py), `__init__`, `graph`, `global_graph`, `db`, `seed` resolve paths/bindings, directly open graph files, keep execution in project SQLite, and seed packaged inference. | Shared files already exist; a persistent owner service and project registry do not. Initialization and seeding must respect the chosen mode before opening storage. |
| [Graph](../src/metaform/graph.py), `get`, `provenance`, `scoped_export`, `scoped_join_references`, `assemble`, and [backends](../src/metaform/backends.py) preserve observations and source-scoped joins. | Preserve these record semantics. `assemble` only walks one physical graph; `composed_search` deduplicates by Element ID and is not the requested closure. |
| [Intake](../src/metaform/intake.py), `_owned`, `_global_lock`, `_commit_inference`, `_finish`, `inference` retain focal snapshots and completion observations. | A service cannot replace `_global_lock` with unrelated HTTP calls: completion check plus global/project writes must remain one serialized service operation; P2 additionally proposes crash atomicity. Type presence differs from inference completion. |
| [Workflow](../src/metaform/workflow.py), `import_workflow`, `Engine.definition`, `Engine.next`; [prompts](../src/metaform/prompts.py), `get`, `snapshot`, `prepare`. | Workflow steps, transitions, condition-rule participants, prompts and snapshots are executable dependencies. Prompt assembly currently uses the project graph only. |
| [CLI](../src/metaform/cli.py), `main`; [MCP](../src/metaform/mcp_server.py), `serve`, `server`; [portable MCP](../src/metaform/portable_mcp.py); [continuation](../src/metaform/continuation.py), `publish`, `begin`; [actor](../src/metaform/actor.py), `gateway`. | Startup must cover ordinary, early `begin`, and assignment-bound paths; the actor gateway is an assignment bridge, not a shared service. |
| [Portable export](../src/metaform/portable.py), `export`, `state_dump`, `import_bundle`, `main`. | Export currently copies all project/global graph data, home assignments and home modules; relocation mainly covers pending work. Packaging also includes package data that could reseed unrelated inference. |
| [History](../src/metaform/history.py), `knowledge_digest`, `checkpoint`. | Digest currently includes the entire global Elements/joins and run data. Unrelated shared changes currently affect project history. |
| [Viewer lifecycle](../src/metaform/modules/viewer.py), `serve`; [viewer](../src/metaform/viewer.py), `create_app`. | Viewer marker existence is not service liveness. Existing workbench is bound to one App. |
| [Schemas](../src/metaform/schemas.py), `registry`, `bundled`; [Registry](../src/metaform/registry.py), `discover`; [sync](../src/metaform/modules/sync.py). | Schemas and custom module assets can live in shared locations; a project export needs dependency selection. Global Git synchronization is a different operation. |

[Serena notes](../docs/serena-reference.md) are an inspected repository reference, not a newly verified claim about that external project's current version. Its recorded read-only multi-project server and single-active-project agent suggest alternatives but do not define Metaform.

## 4. Proposed architecture and responsibility boundary

**P1: one user-local knowledge service per resolved `METAFORM_HOME`, reached by loopback HTTP with versioned JSON operations.** The CLI, MCP and viewer remain clients of the existing application/registry. They submit knowledge operations with explicit project context. The service does not maintain an active project or run model calls.

| Choice | Tradeoff | Recommendation |
| --- | --- | --- |
| Direct embedded database in every client | Minimal change but does not supply the requested running shared service or one knowledge owner. | Preserve only as legacy compatibility during migration. |
| Per-client stdio knowledge subprocess | Simple process ownership but duplicates services and ties service life to a client. | Retain stdio for MCP's external transport, not the shared service. |
| Local socket RPC | Filesystem endpoint ownership; platform-specific socket/pipe handling and less reuse of existing HTTP patterns. | Viable alternative to P1. |
| Loopback HTTP JSON | Uses existing HTTP experience and portable standard-library client facilities; requires explicit endpoint identity and credential handling. | P1, without exposing a remote/multi-user service. |
| User OS service manager | Durable supervisor integration, but install/lifecycle differs by platform. | Later integration if wanted; CLI-managed detached child meets initial scope. |
| Central SQLite knowledge store | One transactional boundary across global and project knowledge; SQL indexes match incident reference lookup. Requires owner-aware tables and migration. | P2. |
| Existing graph file per project plus global graph | A sole-owner service can serialize existing operations and capture a coherent snapshot under one service lock. Preserves present per-store crash behavior without a new transaction coordinator. | Credible smaller alternative, P2-alt. Cross-store crash atomicity is an additional proposed guarantee, not a requirement of the brief. |

**P2: service-owned SQLite knowledge database at `<home>/service/knowledge.sqlite3`, with installed analytical backend copies.** Graph records, project registry, schemas and request receipts share a transaction boundary. Reuse graph normalization, scoped retrieval and similarity algorithms; refactor record access behind an owner-bound adapter. Portable knowledge remains two JSON stores. Existing SQLite/JSON/Ladybug graphs are migration inputs, and standalone legacy operation retains its backend. Ordinary graph reading/editing, join traversal, prompt/workflow operations are the portable parity surface. None uses Cypher as a dependency.

P2 adds cross-owner crash atomicity and durable mutation receipts beyond the brief and present file-lock semantics. That guarantee motivates a single transaction boundary; it is not evidence that P2-alt inherently needs a coordinator. P2-alt can implement the requested service and snapshot behavior by making the service the sole writer, holding one service lock across current completion-check/global-write/project-write operations, and snapshotting all needed backend records before releasing it. It retains the current possibility of a crash between the two store writes and subsequent retry/finish recovery. It avoids central table migration and is a valid implementation choice if preserving that baseline is preferred. P2 is recommended for owner-indexed retrieval and simpler atomic recovery at the cost of a larger storage change. Review should judge whether that extra guarantee merits the change.

**P2a: retain `LadybugGraph` as an optional installed development/analysis copy.** Reuse `open_graph`, `LadybugGraph.put`, and `LadybugGraph.query`. Connected `graph backend` reports both `knowledge_backend: sqlite` and the configured analytical backend. `graph backend --name ladybug` hydrates or refreshes separate owner-specific copies at `<home>/service/analysis/<owner>/metaform.lbdb` from a coherent service snapshot (use `global` or the bare UUID as the filesystem owner directory); the same command reports the copied `source_revision`. `graph cypher` routes the selected project/global owner to that copy and returns its `source_revision` with the result. A copy can be useful even when older than current knowledge, so age is observable rather than an automatic inference gate. No analytical copy is needed to start, prepare a prompt, progress a workflow, traverse, or export.

The explicit refresh operation builds a replacement in temporary storage, then publishes it under a per-copy lock; queries see the previous or refreshed copy, never partial hydration. Copy metadata stores `{owner, source_revision, refreshed_at, backend}`. This is a proposed local snapshot refresh mechanism, not bidirectional synchronization: Cypher changes are confined to the analysis copy, and refresh regenerates that disposable copy from authoritative knowledge. Portable archives omit native database files and run all core operations over captured JSON. They retain the existing capability explanation for an explicit Cypher request. Installed Cypher capability is preserved alongside portable operation; central operational storage does not imply its removal.

**P3: connected execution state remains project-local `.metaform/state.sqlite3`.** Service-owned “local project data” includes the project's knowledge, local inference, prompts, workflows, associations, and registered schemas. Runs, pending assignments, events, workfolders, file history and outputs stay with the client project's execution storage and files. This is an explicit interpretation of R1, proposed for review: the brief fixes portable execution state, but does not settle connected execution state. Centralizing runs instead would require an execution RPC layer and changes to direct `App.db()` users; it is not hidden inside P3.

| Participant | Responsibility |
| --- | --- |
| User/project client | Select/register the project, request operations, display project/mode and service status. |
| Shared service | Own durable global/project knowledge, perform owner-scoped reads/writes and atomic inference commits, compute consistent export closure. |
| Inference agents | Produce the existing source-specific inference; the service records it without changing authored behavior. |
| Workflow engine/harness | Keep existing execution/assignment semantics, perform model/file work locally, submit knowledge operations. |
| Portable runtime | Run the same knowledge interface over JSON, restore local SQLite and materialize bundled assets; no service discovery or connection is needed. |

## 5. Project registration, selection, and lifetime

**P4: stable UUID project identity distinct from filesystem location and history `mform_sha_id`.** Service registry entry: `{project_id, name, path, created, updated}`. The local `.metaform/project.json` stores `{format: "metaform-project/1", project_id, knowledge_mode: "service", service_home}`. The service registry indexes canonical path uniquely. Moving a registered directory uses `project relocate --path`; copying it uses `project connect --new` to create a distinct owner. A copied marker at a second path produces an explicit location mismatch result with these two actions; it does not silently make two different directories one execution context. Portable export retains the original logical `project_id` and `origin_project_id`, and creates a separate local `copy_id`. Explicit ownership references continue to address the same logical project; portable mode never auto-registers or contacts its originating service.

Proposed commands, exposed by a `project` module and the same registry over MCP:

- `project connect`: register/adopt the selected project, copy its current local graph and the current home global graph into the service, then write the local mode marker after verification. Preserve original files.
- `project list`: return registered ID, name, path and knowledge mode.
- `project current`: return selected project, mode, service identity/status and current assignment if present.
- `project relocate --path`: update the selected registration location, leaving knowledge ownership unchanged.

CLI accepts an early `--project <path-or-registered-id>` selector before ordinary parsing. Resolution order is assignment binding, explicit selector, `METAFORM_PROJECT`, current-directory project context. A conflicting selector in a bound assignment reports the existing binding rather than reassigning the workflow. CLI selection lasts for the invocation; there is no global current-project setting. A fresh service-mode project registers on first load; legacy directories keep direct operation until `project connect`. Whether new installed projects default to service mode is P4a, recommended yes; portable markers always choose portable mode. Adoption never occurs merely because a legacy directory was inspected.

An MCP session holds an immutable selected App; `project.select` constructs a replacement session App for subsequent requests. Each in-flight request retains the App/project captured at dispatch. Existing assignment-bound requests retain their binding; project selection changes neither their run nor their project. The workbench shows project name/path and “Shared service” or “Portable”; choosing another registered project navigates to its project-specific URL. The request URL/context identifies the project, so tabs cannot overwrite one another's selection. Run/assignment identity is displayed separately.

The service survives client disconnects, does not start model work, and runs until explicit `service stop` or OS termination. `service status` probes; `service stop` sends an authenticated shutdown request to the verified instance, drains accepted knowledge operations, and closes storage. It never signals a PID copied from a stale marker. Restart changes `instance_id`, preserves durable `service_id`, registry, knowledge and receipts, and leaves local run/continuation state intact. An interrupted model invocation is still owned by its existing harness; service restart alone neither aborts nor duplicates it.

## 6. Service startup and protocol

**P5: authenticated challenge-response plus OS-backed process lock.** Paths below are under the selected home, not a project:

- `service/instance.lock`: held by the child for its lifetime using the existing OS-backed `FileLock` pattern.
- `service/start.lock`: serializes client discovery/start attempts; lock-file existence is irrelevant.
- `service/endpoint.json`: `{service_id, instance_id, protocol: 1, host: "127.0.0.1", port, pid}` written atomically only after database initialization and listener readiness.
- `service/token`: randomly generated user-local credential, reused across restarts, stored with user-only access. PID is diagnostic only.
- `service/service.log`: detached child stdout/stderr, never MCP stdout.

`GET /v1/health?challenge=<fresh-random-value>` with a bearer credential must return HTTP success and `{product: "metaform-knowledge", protocol: 1, service_id, instance_id, ready: true, challenge}` matching the discovery record and challenge. The handler reports ready only after registry and knowledge storage are open. A successful TCP connect, a listener with the wrong identity, old response bytes, wrong credential, a PID match, and a marker do not qualify. This is a same-account local service identity check; it does not claim protection from another process with access to the credential.

Startup algorithm:

1. Resolve mode/home first. Portable mode returns its local knowledge adapter without probing. Service mode reads the endpoint and performs a fresh authenticated health probe (2-second timeout).
2. On success, reuse it. On failure, acquire `start.lock` with a 30-second bounded wait, then probe again: another starter may have succeeded.
3. If the child lifetime lock is held but no probe succeeds, poll readiness within the same startup deadline. Do not start a competing owner or terminate an unverified process. Return `service_unavailable` with the log location when the deadline expires.
4. If no child owns the lifetime lock, spawn `sys.executable -m metaform.service --home <resolved-home>` with stdin detached and output to its log. The child itself acquires `instance.lock` before opening the store; a racing child exits when it cannot acquire ownership.
5. The child initializes/migrates its own schema, binds an OS-assigned loopback port, starts its handler, then atomically publishes the endpoint. The starter verifies the full health response before returning. Other waiting clients acquire the startup lock and verify/reuse it.
6. If startup is interrupted before readiness, the OS releases locks when their owning processes exit. A later client may start again even if files remain. If the starter exits but the child reaches readiness, the next client verifies and reuses it. If a live child remains hung before readiness, report that condition; do not interpret metadata cleanup as successful recovery.

A failed normal request reconnects through the same discovery path. An ambiguous native `analysis.query` response is reported without automatic replay because mutations of that disposable copy cannot share the operational SQLite transaction. Reads can be retried. Mutations use durable request IDs scoped to the request’s project context: retries resend identical envelopes and receive that project’s original result. Reusing an ID with a different body returns `request_id_conflict`. No automatic mutation replay under a new ID occurs after an ambiguous connection failure.

### Operation envelope and API

`POST /v1/operations` accepts `{protocol: 1, request_id, project_id, operation, arguments}`. Successful reply: `{protocol: 1, request_id, project_id, service_id, instance_id, revision, result}`. Error reply: `{protocol: 1, request_id, project_id, error: {code, message, details}}` with a non-success HTTP status. `project_id` is mandatory for project-bound operations; list/register and global-only administration use null. An unknown owner returns `unknown_project`, not the last client's owner. The service derives all local ownership from the envelope. An explicit `owner` argument can name `global` or the envelope's project only, except registry administration.

| Operation | Arguments and result |
| --- | --- |
| `project.register` | `{path, name?, new_copy?}` → registry entry; same path is idempotent. |
| `project.list`, `project.get`, `project.relocate` | `{}` / `{project_id}` / `{path}` → entries or selected entry. |
| `graph.get` | `{owner, id, scope?}` → current record or null; `scope` uses retained source observations. |
| `graph.search` | `{owners, query, layer?, scope?}` → records keyed by owner/ID/source, with independently addressable variants. |
| `graph.joins`, `graph.provenance`, `graph.export`, `graph.stats`, `graph.assemble` | Existing method arguments plus owner; preserve current record contents and observations. |
| `graph.put` | `{owner, graph, source, layer}` → existing element/join counts; normalization unchanged. |
| `graph.rename_elements`, `graph.delete_joins`, `graph.clean`, `graph.similarity`, `graph.merge_perspectives` | Existing arguments plus owner; results retain source separation. |
| `knowledge.assemble` | `{focal, scope?, category?, depth?}` → owner-labelled project/global source graphs, structural similarity separately, and unresolved references. Runtime depth remains a caller's operation choice. |
| `knowledge.snapshot` | `{execution_roots, runtime_assets?}` → immutable selected closure with revision, owner partitions, schemas, dependency manifest and unresolved references, as specified in §8. No export depth parameter. |
| `inference.read` | `{id}` → existing completion status and focal inference graph, preserving snapshots/provenance. |
| `inference.contribute` | `{focal, request_id, graph}` → atomic completed-check and eligible global contribution or existing reuse result. |
| `inference.commit` | `{focal, request_id, snapshot}` → atomic completion check, global contribution/completion observation and project Latent copy, plus durable receipt/reuse result. |
| `schema.get`, `schema.put`, `schema.list` | `{owner, id}` / `{owner, schema}` / `{owner}` → registered schema or owner registry; selected owner follows the same project/global restriction. Preserve existing home registration as global; explicit project registration is local. |
| `analysis.refresh`, `analysis.query`, `analysis.status` | `{owner, backend: "ladybug"}` / `{owner, query, parameters}` / `{owner}` → current copy metadata or `{source_revision, refreshed_at, result}`; installed copies only, as P2a specifies. |

`RemoteKnowledge.call(operation, arguments, request_id=None)` and `LocalKnowledge.call(...)` implement the same dispatcher contract. `BoundGraph(knowledge, owner)` adapts existing graph signatures for `app.graph` and `app.global_graph`. New cross-store operations use `app.knowledge`; existing per-owner callers need not know HTTP. No arbitrary Python execution or raw SQL endpoint is proposed.

`inference.commit` executes in one central SQLite transaction: check the latest focal completion, apply the existing `_contribution` rule, retain source-scoped IDs, save global records and `archaeology-complete`, save the selected project's archaeology contribution, and save the receipt before commit. On already-complete inference, return the retained result and materialize the completed inference for the selected project as the existing completion/finish flow requires. `Intake` retains the per-request accumulated snapshot locally; the service does not receive Contextual joins as latent inference input. A crash after service commit but before local `save_run` is recovered by retrying the same request and updating local run state from its receipt. `inference.contribute` also makes its completion check and write one transaction. No filesystem graph path is exposed through a remote adapter to imitate `_global_lock`.

## 7. Ownership, source records, and storage contract

Ownership, semantic source and physical location are independent axes:

| Axis | Values / meaning |
| --- | --- |
| Owner | `global` or `project:<uuid>`; determines whose joins can expand project closure. |
| Source | Existing observation `source` and join `join_scope`, including `native`, `archaeology`, `authored`, `archaeology-complete`, and structural `merged`. |
| Record identity | `(owner, kind, id)` for current Elements/joins; observations additionally retain their original observation ID/source. |
| Semantic address | Existing Element namespace/ID; not a filesystem path or project UUID. |
| Physical store | Central service SQLite, legacy backend, or portable project/global JSON. |

Service tables extend the current graph shapes with owner keys: `elements(owner,id,entity_desc,entity_schema,entity_json_obj,layer)`, `joins(owner,id,object_id,element_id,type,join_scope,body)`, `participants(owner,join_id,ordinal,role,ref,value)`, `observations(owner,id,element_id,source,record,created)`. Composite primary/foreign keys include owner. Additional tables are `projects`, `schemas(owner,id,body)`, `receipts(project_context,request_id,body_hash,result)` and one revision counter. Receipt primary key is `(project_context,request_id)`, where project context is the explicit project UUID or the reserved global-administration context; the body hash includes operation, arguments and that context. Equal run/request IDs in two projects cannot share receipts. Increment the revision with each committed knowledge mutation; store mutation and receipt in the same transaction. Index owner plus join endpoints/participant ref and observation source. Never use a global ID-only dictionary to overwrite another owner's record.

Current record example, with new ownership in the enclosing partition rather than in semantic payload:

```json
{
  "owner": "project:A",
  "elements": {
    "code.renderer": {
      "entity_desc": "Contextual source description",
      "entity_schema": "metaform:element",
      "entity_json_obj": {"en": "Renderer"},
      "layer": "elements"
    }
  },
  "joins": [{
    "id": "join:source-scoped-digest", "source_id": "render-use",
    "object_id": "workflow:inspect", "element_id": "code.renderer",
    "type": "workflow_attachment", "join_scope": "authored",
    "participants": [
      {"role": "workflow", "ref": "workflow:inspect"},
      {"role": "subject", "ref": "code.renderer"}
    ]
  }],
  "observations": [{
    "id": "observation-digest", "element_id": "code.renderer",
    "source": "native", "record": {
      "entity_desc": "Contextual source description",
      "entity_schema": "metaform:element", "entity_json_obj": {"en": "Renderer"}
    }, "created": "2026-09-08T00:00:00Z"
  }]
}
```

This is a storage fixture, not an inferred semantic definition. `project:A` abbreviates a UUID owner. An independently retained archaeology observation for the same Element can contain a different description/semantic object. `graph.get(owner,id,scope="native")` and `scope="archaeology"` return their respective contents; an edit creates that source's observation without rewriting the other. Source joins keep `source_id`, `authored_id`, and `inference_type` where present. Similarity remains structural; it is neither an ownership edge nor a route that imports semantic payload from another source.

**P6: references remain existing strings with explicit ownership metadata only when needed.** New cross-owner references can add `owner` on a participant; endpoint-only joins use an additive `reference_owners` map keyed by `object_id`/`element_id`. `ref` and endpoint strings keep their authored ID. Explicit owners are precise references. An unqualified reference resolves first within the authoring owner; project-authored references may fall back to global. A global-authored reference resolves in global. For semantic Element addresses, traversal additionally enumerates incident eligible joins at that address across global and selected-project partitions, even when records exist in both. Thus a local view does not hide a shared Type's global relationships. For join identities, incident lookup uses owner-qualified identity so equal join strings from two owners cannot become one relationship accidentally. Existing qualified references must not be re-resolved by precedence on import.

A cross-owner reference to another project's private record stays unresolved for this export with reason `outside_project`; it does not authorize that owner's graph. An eligible join itself travels intact with all participant roles, values, logic and references even when a participant cannot resolve. Missing references are retained and reported with `{from: {owner,kind,id}, field, ref, requested_owner?, reason}`. This is a storage observation, not an inference failure or new model gate.

Source observations for each selected current Element travel in full, including historical records and focal completion snapshots. `archaeology-complete` remains an observation; existence of an Element cannot create a completion marker. Historical snapshot bodies are preserved unchanged. Historical-only references are retained in an archive dependency partition (§8) so replay/provenance remains usable without rewriting the current graph to historical contents. Missing historical contents remain explicitly missing; export does not invent them.

## 8. Project closure and executable dependencies

**P7: closure traverses incident joins in either endpoint direction, including join identities and all participant refs.** This follows current `Graph.assemble` behavior; it is a proposed concrete realization of the brief's “following joins.” Directional role/purpose contents remain unchanged. No fixed traversal depth, namespace-prefix filter, or list of files defines the global extent. Global knowledge can be large when the project is actually connected to a large component.

### Roots and record classes

1. All current selected-project Elements and non-similarity joins, across native, archaeology, authored prompts/workflows/rules and other existing layers, are roots. This retains all local inference, including disconnected local records. All selected-project source observations travel with their owners. A global Type address referenced by any of these records is eligible even if it was never a local file or original intake node.
2. Execution roots come from the selected project's SQLite runs, pending assignment and `assignments` map, saved workflow `stack` frames, focal Type IDs, prepared prompt/schema/rule snapshots, and associated workfolder records. Current installed project module declarations are dependencies. Global procedures only become execution roots when referenced by local graph/work or chosen project modules.
3. Workflow attachments use ordinary reified joins; P7a proposes `workflow_attachment` with workflow/step and subject participants. Imported workflow/step `attachments` arrays are materialized as those joins. Existing relationships remain discoverable through their endpoints/participants without this new type. No authored prompt wording is rewritten to encode an attachment.
4. Current source-graph joins expand the semantic closure. Observations and retained completion snapshots are evidence, not incident edges. Their explicitly stored dependency references are followed to preserve usable evidence and executable snapshots as described below. Similarity joins do not expand the source closure; recompute them from the selected source graphs, retaining provenance references.

### Explicit traversal algorithm

The store offers `record(key)`, `incident_element(address, owners)`, `incident_join(key, owners)`, `resolve(reference, author_owner)`, `source_observations(key)`, and typed `dependencies(record)` from one read snapshot. `resolve` returns logical reference keys even when their bodies are absent, so incident lookup still runs and missing-body evidence is recorded. For a missing unqualified Element reference, retain the address with eligible author/global ownership candidates; do not lose it during fallback. `key` is `(owner,kind,id)`; legal owners for project A are `{global,project:A}`. `incident_element` matches the same semantic address across these two owners; a reference with an explicit different owner never matches through that shortcut. `incident_join` resolves each endpoint/participant reference to an owner-qualified join before comparing. All returned joins retain complete original bodies.

```text
owners = {global, project:A}
queue = every current local Element/join key except similarity joins
queue += resolve each typed current execution root
visited_records = set()
expanded_addresses = set()
current = owner-partitioned empty graphs
unresolved = set()

while queue:
    key = queue.pop()
    if key.owner not in owners:
        record outside_project; continue
    if key in visited_records:
        continue
    visited_records.add(key)
    item = snapshot.record(key)
    if item is a similarity join:
        continue                      # structural records never expand incidence
    # Ordinary missing bodies still permit discovery of incident structure.
    if key.kind == element and key.id not in expanded_addresses:
        expanded_addresses.add(key.id)
        queue += incident_element(key.id, owners)
    if key.kind == join:
        queue += incident_join(key, owners)
    if item is missing:
        record missing; continue       # incidence above still ran
    current.add(item)                  # complete body, never a clipped n-ary join
    observations = source_observations(key)
    current.add(observations)
    if key.kind == element:
        for eligible owner variant at item.id:
            queue.push(variant.key)    # preserves local and global source contents
        latest = latest executable focal completion in observations, if present
        if latest:
            retain latest.inference unchanged as snapshot evidence
            queue += current-resolution keys for every snapshot Element ID,
                     focal ID, and every snapshot join endpoint/participant ref
            # Snapshot-only join bodies remain evidence; their members seed
            # current semantic closure, including incident global/local joins.
    if key.kind == join:
        for ref in endpoints union participant refs:
            queue += resolve(ref, key.owner), recording missing/outside_project
    for dep in typed current dependencies(item):
        queue += resolve(dep, key.owner), recording unresolved

archive_dependencies = retain historical observations/completion snapshots
for each explicit dependency in that retained evidence:
    resolve within owners and retain the exact stored body when available
    recursively follow typed dependency refs with a separate visited set
    retain historical bodies separately from current records
    do not enumerate incident current semantic joins for historical-only refs

schemas, runtime_assets = resolve executable/schema dependencies recursively
similarity = compare(current[project:A].native, current[project:A].archaeology)
return current, archive_dependencies, schemas, runtime_assets, similarity, unresolved
```

Join references use `object_id`, `element_id`, and every `participants[].ref`; `join_participants`' fallback alone is insufficient when explicit participants omit an endpoint. Visit by owner/kind/ID, not bare string. A reached join is itself a traversable vertex, so joins that refer to it are found; a cycle of reified joins terminates. A literal participant `value` is retained but not treated as a reference. A relationship type is never excluded because its name was absent from a predefined semantic list; similarity's structural source is the sole non-semantic exception. Scope/category filters belong to interactive assembly, not export extent.

**Historical dependency proposal P7b:** the latest executable `archaeology-complete` snapshot of each reached focal Type contributes its Element IDs, focal ID and join member references to current semantic roots. If that snapshot names Y and current global Y→Z exists, both Y and Z travel even when the snapshot join is absent from current top-level joins. Preserve historical snapshots intact and recursively retain their explicit referenced records in `knowledge/archive-dependencies.json`; historical-only records do not expand current incident semantic closure. The latest completion that names a no-longer-current global join still carries that exact snapshot join and its required participants as usable snapshot data, while those members seed current traversal as above. Older completion snapshots remain independently readable. In both service and portable `inference.read`, preserve the latest completion’s join list exactly. Resolve its Element members against current global records first, matching existing `Intake.inference`; when no current record exists, use the completion’s captured Element record, then its owner-qualified archive dependency body. Report unresolved if none exists. This fallback does not overwrite current records or substitute current joins for snapshot joins. Older completion snapshots and ordinary historical-only references do not seed current incident traversal. This chooses reproducible completion/history over silently truncating stored evidence. Whether historical-only dependencies should instead seed full current incident traversal is a consequential alternative for review; it would enlarge the archive and change history sensitivity.

### Shared object example

Fixtures: A owns workflow W and authored attachment W→X. Global owns X, Y, Z, global join g1 X→Y, and archaeology join g2 Y→Z. B owns local join b1 X→Q and Q. A also owns local archaeology join a1 Z→L, where L is outside A's original intake contents.

Starting at A's local roots selects attachment W→X; global g1 selects Y, g2 selects Z, and A's a1 selects L. B's b1 is ineligible at X, Y, Z, and every later lookup; Q is absent. If global X→Q is later authored, Q becomes related through that global join and legitimately travels, while b1 still does not. Reified g3 can join g1, Z, and a condition-rule Element; all three participants and g3's contents travel. Reciprocal references g3↔g4 terminate through the qualified visited set. Dotted ancestry alone does not fabricate a join to another node.

### Typed executable references and archive membership

`dependencies` reads schema-defined fields, not arbitrary string matching in prose. Built-in extractors cover:

- workflow `workflow_step`, `transition`, `step_prompt`, condition-rule refs; `kind: call` uses `step.workflow`; `kind: parallel` uses string branch workflow IDs, `branches[].workflow`, or recursively embedded `branches[].steps`; `step.focal` uses the prepared value where one exists;
- `prompt_ref`, attached semantic `rule_codes`, response schemas and recursive registered `$ref` targets; inline snapshots retain exact text/rule revisions;
- current intake focal completion snapshots and saved run `stack[].definition`, `pending`, `assignments`, retained prepared inputs and module IDs;
- `file:` prompt contents for every retained workflow step, including future unissued steps, are captured at the saved workflow definition’s `base_dir` (or project path), including external directories. Materialize them under bundled `resources/workflows/<workflow-revision>/`, resolve executable `file:` references through the portable home’s `resources.json` mapping to the materialized files. Preserve authored references and saved source locations; this avoids changing source records or their digest during relocation. A known unavailable file is reported as an unresolved runtime dependency rather than guessed. Already prepared prompt snapshots retain their exact text. Future dynamic focal values use bundled captured knowledge; arbitrary future references cannot make unseen service data available offline;
- registered module manifests/handler assets, explicit module dependencies, and recorded module resource paths.

Available module and command manifest metadata is supplied in `knowledge.snapshot.runtime_assets`; only referenced or configuration-selected capabilities enter the closure and extend it through their declared knowledge references, within the same knowledge revision.

For custom modules P7c adds optional manifest `portable` metadata: `files` (relative assets/dependency files) and `knowledge_refs` (explicit graph references). Built-in modules provide equivalent extractors. All project-local module files remain project assets; shared custom modules selected by project configuration, graph procedures or retained runs bring their own directory and declared dependencies. Merely being installed in another project's home namespace does not select a module. Known missing declared resources and references outside the portable project are reported as unresolved runtime dependencies. Arbitrary undeclared handler dependencies cannot be discovered by this mechanism.

Copy assignments only when their stored project identity/path and `(run_id,request_id)` match the selected project's retained run jobs; include completed retained jobs if their continuation evidence is retained. Select home workfolder baselines by selected `workfolders` rows, not by copying the entire home directory. Preserve project outputs/history. Bundle only effective project-associated schemas plus their recursive references. Standard runtime modules/semantic source texts are infrastructure assets; package `data/global` inference and schema seed indexes must be filtered to this snapshot or omitted and replaced by the selected bundle data. Otherwise `App.seed`/`schemas.registry` could reintroduce the complete packaged global graph offline.

### Snapshot and digest consistency

**P8:** `knowledge.snapshot` walks the selected closure inside one SQLite read transaction, establishing its revision on the first read. Concurrent committed writes after that revision do not appear halfway through traversal. Index-backed incident queries avoid materializing every global record. Cost is proportional to selected records/references plus selected local roots; closure may legitimately approach the full store. JSON builds an in-memory incident index once per snapshot and uses the same traversal.

The client takes the proposed project snapshot lock before capturing execution roots/state and requesting the knowledge snapshot; all short run/state/workfolder mutations participate in a new project snapshot lock, acquired before existing run locks. Acquire it at the outer transition boundary and reuse one reentrant acquisition context for nested writes in that same project: `Engine.next` calling `App.save_run` must not construct and acquire a second independent FileLock for the same path. Direct mutations outside a transition acquire that same project context. Hold no such lock during model calls. Release after copying state, snapshot and selected asset bytes to temporary export staging. Archive compression happens afterward. Shared store writes from other projects can proceed under SQLite snapshot isolation. Mutable project/workfolder files use manifest hashes before and after copying; if bytes change, return the concrete changed paths and retry the capture, not a silently mixed successful export. This is an export consistency condition, not a model-output condition.

Add `knowledge_digest_version: 2`. Digest canonically ordered selected project/global source records, their observations/completion evidence, selected historical dependencies, schemas and normalized run data. Exclude service revision/instance IDs and unrelated global records; preserve existing normalization for relocation/nonce data and extend it across every assignment/stack-frame path. The archive and its export checkpoint use this exact snapshot/digest, not two fresh reads. Prior history digests retain their recorded version; do not rewrite old checkpoints. New checkpoints retain the selected global knowledge snapshot as well as project knowledge so their recorded digest can be explained. Unrelated shared additions cannot change the selected digest unless an eligible relationship or explicit dependency connects them.

## 9. Portable runtime behavior

**P9: `metaform-export/2`**, retaining `knowledge/project.json`, `knowledge/global.json`, history/files and continuation layout, adding `knowledge/archive-dependencies.json`, an ownership/reference manifest, selected assets/schemas, source revision and `origin_project_id`. The portable semantic owner remains `project:<original UUID>`; `project_id`/`origin_project_id` preserve that UUID and a separate `copy_id` identifies the independent working copy. Global partition now means the captured global knowledge available to this copy, including new global inference authored locally after export. It never implies a connection back to the shared service.

`import_bundle` writes portable mode before constructing App or seeding; restores raw source observations and join IDs without manufacturing an `imported` semantic source as a replacement; creates local SQLite and relocates the entire run/assignment/workfolder/continuation structure. Use one relocation routine for `pending`, every `assignments` value, `stack` frames and stored gateway/workfolder paths, assignment files and `.agentid` records inside retained workfolders. Clear ephemeral executing-process/gateway/viewer state so a process that was not copied is not presented as live; preserve pending work, answers, receipts and source prompt snapshots. Recreate continuations from retained jobs without rebinding unrelated assignments.

`App.seed` in portable mode loads built-in runtime prompts/rules when required by existing seeding behavior, but only the captured global inference seed; no ambient home or service registry lookup. Module discovery uses bundled home/project modules and rewritten bundled module paths. All graph knowledge mutation uses JSON and existing file locks; SQLite contains only execution state. Portable MCP keeps the existing host-answer loop. The copy supplies prompts and schema data without embedding a model, credentials, native Ladybug engine or external image service. Existing optional schema-validation limitations remain visibly reported through `schemas.annotations`; this proposal does not certify unsupported native/dependency capabilities as portable.

Offline sequence, after making the originating service/home unavailable:

1. `python <archive> graph get --id code.renderer --scope native` reads captured Contextual contents; archaeology reads the independent record. `graph put` changes only the chosen source and survives the next invocation.
2. `prompt prepare` resolves its original operation, selected graph meaning, exact rule revisions and schemas from JSON/bundled files.
3. `python <archive> begin <nonce>` resumes the correct pending job; submitting an answer and requesting the next step progresses the stored workflow using local SQLite.
4. A workflow condition resolves its bundled rule and a nested workflow resolves its captured definition. New inference can be supplied by a host agent through the normal answer loop.
5. `python <archive> package export --path <continued-archive>` captures modified JSON, SQLite execution state, file work and continuation history. That new archive independently materializes and continues the same work.

## 10. Compatibility and migration

`project connect` reads legacy graph exports using their configured backends, preserves the original files, and writes owner-qualified records in one service transaction. Global import is associated with the source home and source digest so subsequent registrations do not repeatedly overwrite the same imported corpus. Source/current record conflicts in an already populated service are returned with both record identities and contents for the migration choice; do not infer a semantic reconciliation policy. This initial migration conflict choice is separate from ordinary new inference behavior. After successful counts/source-content verification, atomically write the project's service marker; failure leaves legacy operation usable. Explicit existing global definitions remain stored unchanged under the current intake promotion rules.

Read `metaform-export/1` and `/2`; `/1` lacks ownership metadata and is interpreted as one project plus its supplied global partition, preserving its historical broader extent. Re-export from `/1` uses the new selected closure. Preserve existing inclusive-history replacement and divergent-history sibling behavior in `import_bundle`; importing an archive makes/updates a portable working copy, not the registered shared owner. A v2 copy imported beside a connected directory remains portable unless a later, separately designed reconciliation/registration action is requested. Do not reinterpret `modules/sync.py`'s Git merge as that protocol.

## 11. Acceptance scenarios

These are commissioned implementation checks, not claims that the feature exists. Unit fixtures use opaque IDs A, B, X, Y, Z as storage identifiers, not new Type definitions.

| Scenario | Starting records/action | Observable result |
| --- | --- | --- |
| A1 — startup/reuse | Empty service home; launch service-mode CLI, then MCP. | Both return the same verified instance ID; one child owns storage; graph operation succeeds only after ready health response. |
| A2 — stale/racing starts | Leave endpoint/PID/lock files after child exit; run eight clients concurrently. Repeat with an unrelated HTTP listener and wrong challenge/credential. | Stale files/listener never count as live; one service owner and all successful clients agree on instance; no PID-based kill. Starter interruption and child interruption recover as §6 specifies. Hung live child produces bounded unavailable result. |
| A3 — isolation and reuse | A and B share global X. Each owns different native X contents and a running workflow with equal fixture run IDs. | Per-request owner selects independent contents, runs and responses. Global X is reusable. Switching one MCP session/tab leaves the other's pending request with its original App. |
| A4 — external workflow/latent closure | Use W→X, global X→Y, archaeology Y→Z and A-local archaeology Z→L from §8. | W,X,Y,Z,L and every selected relationship travel despite Z/L being outside original contents. Prompt and workflow lookup can resolve these records offline. |
| A5 — other project joins | Add B-local X→Q with distinct source content. | A exports neither B's join nor Q unless another eligible relationship reaches Q. Explicit B-qualified refs are preserved as `outside_project` without traversing B. |
| A6 — reified/cyclic completeness | Global g3 has participants g1,Z,rule; g3/g4 refer cyclically; one participant is missing. | Complete joins/roles/logic retained once per qualified identity; every available participant resolves; missing ref is reported; traversal terminates. Include same join ID in A and global to test qualification. With missing X body but available global X→Y, Y still travels and missing X remains reported. |
| A7 — independent sources | Native and archaeology X descriptions and same-authored-ID join purposes differ; similarity shows matching structure. | Scoped connected and offline reads retain each description/purpose/provenance. Similarity has only structure and refs with `11`, never semantic reconciliation. |
| A8 — offline continuity | Export a running nested workflow with multiple intake assignments, prompt/rule snapshots, a future `file:` step under an external `base_dir`, and a Git workfolder; service DB/home unavailable; use empty Python environment and no Git. | Read/edit JSON, prepare prompt, evaluate supplied condition, resume correct nonce, submit and advance using local SQLite, export again, and continue returned archive. No service startup or ambient seed access. |
| A9 — irrelevant shared additions | Record A's closure/digest; add unrelated global U→V and B-local X→Q, unrelated shared assignment/module and packaged inference. | Selected global JSON and digest stay identical; no U,V,Q/B assignment/shared asset appears through ZIP packaging or reseeding. |
| A10 — consistent concurrent export | Pause traversal after its first read; another client commits X→N; resume. | First export contains one revision's complete before-state; later export includes N. Checkpoint digest matches serialized snapshot. |
| A11 — atomic inference/retry | A and B complete same focal X concurrently; interrupt a response after commit; retry same request. | One completion transaction wins, independently retained project Latent results remain usable, retry returns its project-scoped receipt, and no half global/project commit occurs. Equal request IDs in A/B cannot return the other project’s result. Existing global definition protection remains. |
| A12 — history and dependencies | Latest completion references historical join h, Element Y and rule schema s; h no longer exists among current joins, but current global Y→Z exists. An older completion alone references O. | Latest snapshot members seed current traversal, so Y→Z and Z travel; O remains historical-only dependency material. Completion joins remain exact; Element reads prefer current global records then captured records. Missing bodies remain explicit; current source graph is not replaced by old contents. |
| A14 — analytical capability | Hydrate a Ladybug copy at revision r, commit new operational knowledge at r+1, query then explicitly refresh. Disable Ladybug and export/run offline. | Cypher remains available against the installed copy, reports r then r+1 after refresh; every core and export operation also succeeds without the copy or Cypher. |
| A13 — migration/import | Connect each legacy backend with divergent native/archaeology records; import old and new archives; move/copy a marker. | Source records preserved, legacy originals retained, mode changes only after success, ownership/location actions are explicit, archive import performs existing history behavior without shared reconciliation. |

## 12. Decisions for review and evidence limits

| Decision | Recommendation and reason | Alternative / impact |
| --- | --- | --- |
| P1/P5 service interface/lifecycle | User-local loopback HTTP, detached service, authenticated challenge and two OS-backed locks; reuses the Python chassis without installation of a supervisor. | Local sockets or OS service manager; plan tasks 3–4 change. |
| P2/P2a physical knowledge storage | Central owner-partitioned SQLite plus optional Ladybug analysis copies; added crash atomicity is proposed, while core operation remains independent of Cypher. | P2-alt reuses existing owner stores under a sole-writer service lock and preserves current crash/retry semantics without a coordinator. Tasks 2,5,6,9 change substantially. |
| P3 connected execution location | Keep project-local SQLite/files while service owns all knowledge; smallest preservation of existing harness/continuation model. | Centralize execution state as well; tasks 4,5,7,8 require execution RPC and file ownership design. |
| P4/P4a selection/default | Stable registration; explicit legacy adoption; service mode for new installed projects; per-request/session/tab selection. | Opt-in service mode for every project; task 4 startup defaults change. |
| P6 shared Type resolution | Preserve local/global/source variants and qualified references; existing promotion behavior unchanged. | Semantic enrichment/reconciliation of existing shared Types is still undeveloped and is not implemented by this plan. |
| P7/P7a extent/attachments | Undirected incident relationship closure plus explicit workflow attachments and typed executable refs. | Directional traversal or different attachment representation would change tasks 1,6–8 and A4–A6. |
| P7b historical dependencies | Retain exact evidence and explicit dependency closure separately; historical-only refs do not seed full current incident traversal. | Full historical-root traversal yields larger export and broader digest sensitivity; tasks 6–8 change. |
| P7c custom modules | Carry selected module directories plus explicit portable dependencies; report known missing declared resources. Undeclared handler dependencies are not automatically discovered. | Full arbitrary dependency capture is not specified; tasks 7–8 depend on this capability boundary. |

The recommended design was accepted and implemented on 2026-09-08; alternatives are retained as design history. Storage approval does not amend the semantic contract. Baseline inspection and planning evidence remain recorded in the plan; implemented source, distribution and browser verification is recorded in [docs/verification.md](../docs/verification.md).
