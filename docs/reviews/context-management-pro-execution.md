# Execution evidence for the context-management Pro handoff

This appendix investigates the current implementation. It does not approve or implement a role, skill or scheduler reorganization. Runtime investigation starts from `f63cc2e55a9f5416abc20dc0d66413055f53d551`. This preparation additionally corrects legacy generated-role source references in roles.py; the remaining runtime architecture is unchanged. Prompt/skill reconciliation is part of the same preparation. Text measurements below identify that authoring snapshot separately. The live inventory was observed at `2026-10-23T16:29:36Z`. The [exported inventory](context-management-role-inventory.json) contains six configured execution roles, 23 authored framework responsibilities and 39 specialties in this Metaform project's current provider registry. The specialties are project/home data, not a repository-wide constant. Their exported purposes support the provisional classifications below. Their complete selected duties require inspection before a migration decision. These are local evidence paths, not an assertion that GitHub already contains the latest revision. A remote-only reader needs the exact handoff source snapshot and inventory export.

The preceding native measurements are historical evidence preserved in `29cd88bd`. The subsequent tool-instruction prerequisites, regional context and shared-rule changes represented by `f63cc2e5` were not remeasured with native inference. No new paid inference was run for this appendix.

## What actually creates execution work

| Action | Current implementation | What can be counted |
| --- | --- | --- |
| Resolve an authored role | `RoleService.resolve` selects provider contributions and prompt-store components. It does not launch an adapter. [roles.py:102](../../src/metaform/modules/agents/roles.py#L102) | Resolved text and source identity, not an agent or model request. |
| Publish generated expertise | Saves the selected duty and project definition/history, adds common and specialist components, then emits `agent.role.changed`. [roles.py:176](../../src/metaform/modules/agents/roles.py#L176) | A reusable definition, not automatically one session per definition. |
| Create an assignment | Records work, parent/team/GC identity, requested result, return route, specification, candidate and operational `execution_role='worker'`. [state.py:307](../../src/metaform/modules/orchestration/state.py#L307) | An assignment is an accountable contribution. Its identity is independent of whether its procedure is prose, a skill or an authored duty. |
| Delegate a contribution | `_delegate` creates child work/assignment and queues a launch transition. `continue_from` can attach related episode state. [state.py:1131](../../src/metaform/modules/orchestration/state.py#L1131) | A managed execution request. It may wait, reuse eligible context or start fresh. A new responsibility name alone does not determine process count. |
| Launch or resume managed work | Transport checks assignment/runtime/workspace state and advertised load/resume support. Eligible related work reuses its conversation. Otherwise it starts fresh. [orchestration.py:250](../../src/metaform/modules/dispatch/orchestration.py#L250) | Runtime reuse depends on actual adapter and workspace compatibility, explicit episode continuity and settings. |
| Start dispatch | `start_runner` launches a detached Python runner with `subprocess.Popen`. [dispatch:4225](../../src/metaform/modules/dispatch/__init__.py#L4225) | A runner process and capacity lease. |
| Open the ACP adapter | `Session.open_agent` starts the adapter subprocess. The runner then requests `new_session`, or `resume_session`/`load_session`. [runner.py:4173](../../src/metaform/modules/dispatch/runner.py#L4173), [runner.py:3780](../../src/metaform/modules/dispatch/runner.py#L3780), [runner.py:4252](../../src/metaform/modules/dispatch/runner.py#L4252) | Process startup, adapter initialization and native conversation identity are separate quantities. Adapter internals may have further processes. |
| Send assignment or follow-up | The runner calls `conn.prompt` once per queued ACP turn. [runner.py:4961](../../src/metaform/modules/dispatch/runner.py#L4961) | One ACP turn may contain many native model requests and tool exchanges. It is not a token or billing unit. |
| Prime adapter options | Explicit priming opens a session with no MCP server or prompt to inspect advertised choices. [dispatch:7255](../../src/metaform/modules/dispatch/__init__.py#L7255) | Session/process overhead can exist without an inference prompt. The archived benchmark excludes its catalog-prime session from work-session counts. |

Authored-role text reaches fresh managed work through `current_guidance`, normally using the assignment's pinned role snapshot. Shared rules, gateway guidance, duty components and applicable context use the existing recipient ledger. [runner.py:4542](../../src/metaform/modules/dispatch/runner.py#L4542) The immediate functional region uses actual joins, stable address labels and the existing Mermaid renderer. It rides startup or a related-card delta, with unchanged regional content suppressed. [runner.py:4127](../../src/metaform/modules/dispatch/runner.py#L4127) Receipts record actual outgoing components after ACP acceptance. [runner.py:4654](../../src/metaform/modules/dispatch/runner.py#L4654) This confirms shipped content, not retained comprehension.

## Skills do not intrinsically mean fresh agents

The canonical skill registry has nine folders in this checkout, seven discoverable and two address-only: `import-workflow`, `prompt-efficiency`, `scan`, `sentinel` (address-only), `work-evidence`, `workflow-builder`, `workflow-efficiency`, `workflow-evaluator` (address-only), and `write-workflow`. `catalog()` reads their authored metadata. [skills.py:44](../../src/metaform/skills.py#L44)

`metaform_skills op=load` returns the named procedure, required libraries and file names. `op=read` reads a selected file. These functions start no managed assignment, adapter or model request. The agent's decision to request and consume that tool response can still require inference. [server.py:563](../../src/metaform/modules/mcp/server.py#L563), [skills.py:126](../../src/metaform/skills.py#L126)

`skills.served` assembles selected procedure text, current libraries and optional input bound as data. `workflow serve` returns it to an already connected caller without a workflow run record. Dispatch also uses this mechanism to prepare a sentinel's first turn after the sentinel's separate session has already been chosen. Thus serving a skill is compatible with either an existing context or a newly created context. [skills.py:138](../../src/metaform/skills.py#L138), [workflow:436](../../src/metaform/modules/workflow/__init__.py#L436), [dispatch:1892](../../src/metaform/modules/dispatch/__init__.py#L1892), [runner.py:3926](../../src/metaform/modules/dispatch/runner.py#L3926)

Workflow transport makes another distinction:

- `workflow call` appends a callee frame in the existing run. [workflow:235](../../src/metaform/modules/workflow/__init__.py#L235), [executor.py:109](../../src/metaform/modules/workflow/executor.py#L109)
- `workflow handoff` calls `executor.call(..., fresh=True)`, which makes a child **run record** and marks the parent waiting. `_handed` returns a run ID and authored handoff text. These producer functions do not launch dispatch. [workflow:197](../../src/metaform/modules/workflow/__init__.py#L197), [workflow:245](../../src/metaform/modules/workflow/__init__.py#L245)
- `workflow parallel` similarly creates independent child runs and returns handoff descriptions. `workflow assign` creates an assignment-kind run and a resume command. Those records alone do not prove that a host has started separate native sessions. [executor.py:129](../../src/metaform/modules/workflow/executor.py#L129), [workflow:255](../../src/metaform/modules/workflow/__init__.py#L255), [workflow:446](../../src/metaform/modules/workflow/__init__.py#L446)

Fresh-agent intent must therefore be followed through the interpreting agent or host's actual assignment/dispatch route. No automatic native-dispatch consumer was established by the inspected producer paths. Do not infer a session, process or model request from a child workflow run ID. The handoff transport test creates and redeems child runs, rather than launching a model. [test_workflow.py:39](../../src/metaform/modules/workflow/tests/test_workflow.py#L39)

Some skill content itself requests independent execution. The shipped evaluator says to use a fresh evaluator when independent judgment is needed and return a replacement run when it authored the judged work. The builder directs certain judgments through a fresh evaluator. Changing a delivery wrapper alone would leave those instructions in force. These are shipped-source observations, not a claim about an unknown selected override in a live home. [evaluator:15](../../src/metaform/skills/workflow-evaluator/references/procedure.axiom#L15), [builder:21](../../src/metaform/skills/workflow-builder/references/procedure.axiom#L21)

One source-selection distinction also needs an explicit Pro decision: `workflow skill` reads `skill_registry.procedure`, the raw authored procedure, whereas universal `skills.load`, native deployment and `served` use selected prompt-store procedure text. Preserve deliberate source semantics or reconcile them explicitly. [workflow:406](../../src/metaform/modules/workflow/__init__.py#L406), [skills.py:77](../../src/metaform/skills.py#L77), [skills.py:120](../../src/metaform/skills.py#L120)

## Facilitator and helper economics

Specialist routing already sends purposes and a structured local functional graph rather than every duty body. It caches a fingerprint of the ticket/graph and specialty metadata. A sufficiently certain JEV match chooses an existing specialty. Missing credit/provider, uncertainty or no suitable match commissions the Facilitator. [routing.py:120](../../src/metaform/modules/orchestration/routing.py#L120), [routing.py:150](../../src/metaform/modules/orchestration/routing.py#L150)

The Facilitator commission creates its own work, authored responsibility and launch transition. Its compact task points back to the original ticket instead of duplicating its potentially large contents. The Facilitator may select existing expertise, publish a new definition or choose runtime options. Publication continues the original ticket and returns through its recorded caller. That separate commission can incur runner/adapter/session startup, context delivery, tool reads, native inference and return delivery. Neither the price nor the number of model requests is a constant established by this code. [state.py:1288](../../src/metaform/modules/orchestration/state.py#L1288), [state.py:1407](../../src/metaform/modules/orchestration/state.py#L1407), [state.py:1448](../../src/metaform/modules/orchestration/state.py#L1448)

Facilitator/legacy role-creator work and explicit `dispatch_helper` work use the separate bounded helper capacity. Ordinary specialist delegation uses worker capacity. A helper has no ticket, but still has a managed runner, visible thread, adapter, accounting and a brief. Avoid describing it as free or as a same-context skill invocation. [dispatch:4022](../../src/metaform/modules/dispatch/__init__.py#L4022), [dispatch:7064](../../src/metaform/modules/dispatch/__init__.py#L7064)

The current implementation can avoid a separate Facilitator inference session when existing routing confidently selects registered expertise and runtime preparation succeeds without a commission. That is reuse of existing routing, not evidence that every classification or authoring task should run inline. The native efficiency workload explicitly excludes selector/planner overhead, so it cannot price this alternative. [comparison configuration](acp-native-efficiency-comparison.json)

## Discovery, delivery and compaction

Native installation deploys only discoverable skills to verified harnesses with known native discovery support. It writes selected procedures and current library bytes and records exact file hashes plus completion/version metadata. `skills_deployed` verifies that record and the files. It establishes deployment, not that the model read or understood any skill. [install.py:779](../../src/metaform/install.py#L779), [install.py:832](../../src/metaform/install.py#L832), [install.py:854](../../src/metaform/install.py#L854)

With `skill_index=auto`, verified current deployment suppresses Metaform's fallback index. Missing, modified or incomplete deployment keeps fallback discovery. The host may independently inject a native skill catalog. Seven discoverable Metaform skills must not be confused with the archived native host catalogs of 26 or 36 entries, which also include other skills/plugins. [server.py:603](../../src/metaform/modules/mcp/server.py#L603), [historical native payload observations](acp-context-implementation.md#native-inference-follow-up-2026-10-23)

`f63cc2e5` adds operation-level instruction components for module rules, tool/op usage, canonical schema and module-provided usage. A tool with due usage returns `instructions_required` before execution. Explicit resource/help retrieval queues those exact components for response-body receipts. Existing user-configured role restrictions and dynamic withheld surfaces remain distinct controls. [server.py:1257](../../src/metaform/modules/mcp/server.py#L1257), [server.py:1301](../../src/metaform/modules/mcp/server.py#L1301), [server.py:1330](../../src/metaform/modules/mcp/server.py#L1330), [server.py:1727](../../src/metaform/modules/mcp/server.py#L1727)

These tool-usage receipts establish which rendered instruction bodies survived response shaping. They do not establish comprehension. They also do not automatically establish that the procedure returned by `metaform_skills op=load`, all its referenced files, or a native-loaded `SKILL.md` was recorded as a selected procedure component. `skills.load` resolves a selected procedure but does not itself queue that procedure as a context component. `served` records served prompt versions only where a collector/transport actually consumes them. A future change must trace exact recipient delivery rather than treating file availability or helper invocation as proof. [server.py:1685](../../src/metaform/modules/mcp/server.py#L1685), [skills.py:126](../../src/metaform/skills.py#L126), [prompt_files.py:613](../../src/metaform/prompt_files.py#L613)

Observed identified ACP compaction advances the content epoch once. Discovery and legacy guide history can persist while exact content/usage eligibility follows the new epoch. Restoration uses needed resources or references instead of rebuilding the whole assignment on every turn. A summary or marker does not disclose which semantic content survived. Native skill catalogs may be injected again by the host independently. [runner.py:2054](../../src/metaform/modules/dispatch/runner.py#L2054), [shown.py:77](../../src/metaform/shown.py#L77), [roles.py:210](../../src/metaform/modules/agents/roles.py#L210)

## Inventory and provisional classification

All classifications in this section are proposals for examination. A method that can be supplied as a skill can still be used inside a separately assigned contribution. Conversely, retaining an assignment identity does not require creating a new persona or conversation for every method step. Preserve actual ownership, source intent, candidate identity, return routes, configured user controls and specifically requested independence.

### Six configured operational roles

The six names come from [settings.py:862](../../src/metaform/settings.py#L862) and the frozen inventory. They describe execution context rather than six interchangeable expertise prompts.

| Name | Current function | Candidate treatment for Pro |
| --- | --- | --- |
| `intake` | Maps the AUE from source. | Preserve the dedicated intake semantics. Keep the canonical intake fixed. A role-label cleanup must not rewrite this procedure. |
| `system` | Person-facing project conversation and board responsibility. | Retain reachable conversation identity. Planning/interview methods may be loaded into that context where useful. |
| `sentinel` | Takes up a person-raised issue at a map node. | Already receives a skill. Examine whether a separate session is useful for this contribution, rather than relabeling it as a skill and assuming startup disappears. |
| `talk` | Person conversation about a clicked subject, without a ticket. | Retain subject/session routing independently of the method supplied. |
| `prep` | Merge preparation in the relevant workspace. | Procedure candidate within existing integration work, conditional on preserving workspace and caller boundaries. |
| `worker` | Executes ticket work at its functional location. | Retain execution and work attribution. Load selected methods without requiring a new worker for each method. |

There is an additional runtime value: `runner.role` also returns `helper` for helper work IDs, although `AGENT_ROLES` lists six configured labels. The inventory is correct for that configured enum, not an exhaustive count of every value the runner can emit. [runner.py:351](../../src/metaform/modules/dispatch/runner.py#L351)

### All 23 authored framework responsibilities

These are provider-declared responsibilities with `specialist=False`, not the 39 selectable specialties. Their current source is [ROLE_DUTIES](../../src/metaform/modules/orchestration/__init__.py#L31). Proposals are based on declared purpose and the execution paths above.

| Responsibility | Candidate treatment and reason |
| --- | --- |
| `roundtable_follow_through` | Coordination responsibility with procedural presentation/preparation steps. Examine continuity with its actual roundtable caller before moving those steps into a skill. |
| `triage` | Retain person-facing accountability. Interview, planning and ticket-writing procedures are candidates for selective methods within it. |
| `gc` | Retain delivery ownership and return identity. Coordination techniques can be skills without discarding assignment accountability. |
| `functionality` | Independent functional assessment responsibility. Compare its purpose with `harsh_critic`, but preserve the different recorded review/GC relationships until reconciled. |
| `investigator` | Investigation procedure candidate when the current worker already has the needed evidence. Separate contributions remain useful for distinct traces or expertise. |
| `requirements` | Requirements procedure candidate during planning. Retain separate assignment when resolving a distinct contribution adds value. |
| `planner` | Planning procedure candidate in the active context for local work. Separate planning can serve consequential dependencies or unresolved design decisions. |
| `interviewer` | Interview method candidate in the person-facing conversation. Preserve deliberate long-running interview or delegated research contributions where useful. |
| `decomposer` | Task-decomposition method candidate near the existing plan. Preserve actual work identities, board placement and dependency ordering. |
| `specialist` | Already a shared component of generated specialist duties. Keep common execution/result guidance composable rather than commissioning this label as expertise. |
| `harsh_critic` | Preserve requested independent assessment. Naming overlap with `functionality` is a review candidate, not proof their routes can be aliased. |
| `implementer` | Generic implementation duty. Examine overlap with shared `specialist` guidance and domain profiles without removing execution identity. |
| `verifier` | Verification method candidate for self-checks. Preserve an independent assignment when independence is the requested outcome. |
| `reviewer` | Review procedure candidate, with the same explicit independence distinction. Compare overlap with verifier and critics against their actual criteria and routes. |
| `integrator` | Integration procedure candidate with existing delivery owner. Preserve candidate/workspace identities and concurrent-change handling. |
| `architect` | Design contribution or method, depending on scope. Retain distinct expertise for consequential cross-system design questions. |
| `designer` | User-journey/design method candidate. Separate specialist contribution remains useful where the current worker lacks design expertise. |
| `researcher` | Research procedure candidate for bounded lookups. Distinct research questions can justify separate work and parallel execution. |
| `synthesizer` | Synthesis method candidate where the current caller already holds the sources. A separate contribution may help when reconciling independent returns. |
| `dogfood` | Product-use method candidate. Preserve genuinely separate observation or environment needs, rather than assuming the implementer supplies equivalent evidence. |
| `release` | Release-preparation method candidate. Preserve explicit publication authorization and operational boundaries. |
| `facilitator` | Keep reusable-role registry/runtime commission responsibilities explicit. Examine whether selection, creation and runtime choice need separate inference on each actual path. |
| `role_creator` | Explicit legacy compatibility candidate: new commissions use `facilitator`, and both reference `role_creator` prompt content. Retain old assignment/source references during any transition. |

The overlap proposals do not authorize deletion. In particular, `_delegate` treats `functionality` differently from a `harsh_critic` child, and legacy role-creator assignments remain recognized in capacity and commission paths. [state.py:1134](../../src/metaform/modules/orchestration/state.py#L1134), [dispatch:4036](../../src/metaform/modules/dispatch/__init__.py#L4036)

### All 39 observed project specialties

Every name below is from the frozen [inventory artifact](context-management-role-inventory.json). The purpose metadata supports a domain boundary, not a complete duty-equivalence judgment. Suggested overlap groups are comparisons for Pro, not preselected merges.

| Specialty | Evidence-backed candidate classification |
| --- | --- |
| `agent_communication_engineer` | Retain communication expertise. Compare shared transport procedures with async transport and orchestration specialties. |
| `agent_harness_integration_engineer` | Retain adapter/harness expertise. Harness replacement and runtime-choice migration are broader than a generic invocation skill. |
| `async_event_worker_engineer` | Procedure candidate for isolating upstream polling. Compare with async transport while retaining worker lifecycle requirements. |
| `async_transport_engineer` | Retain transport expertise, including buffering, ordering and shutdown. Common diagnostic methods may be shared skills. |
| `browser_performance_engineer` | Retain performance expertise. Profiling/indexing methods are procedure candidates without merging all rendering duties. |
| `cache_invalidation_engineer` | Retain dependency/visibility expertise. A shared invalidation checklist is a procedure candidate. |
| `character_motion_engineer` | Retain procedural motion expertise. Do not merge into generic browser performance on name overlap. |
| `context_delivery_engineer` | Retain context/receipt expertise. Compare startup/onboarding procedures with onboarding and instruction maintenance. |
| `data_migration_engineer` | Strong transactional migration procedure candidate. Retain specialist judgment for data preservation and reversibility. |
| `dispatch_lifecycle_engineer` | Retain lifecycle/stop/recovery expertise. Compare common procedures with dispatch orchestration before merging. |
| `dispatch_orchestration_engineer` | Retain durable assignment/dependency expertise. Existing lifecycle overlaps need complete-duty comparison. |
| `embedded_engine_module_engineer` | Retain embedded engine lifecycle expertise. Share module ownership procedures with module lifecycle, without assuming equal engine knowledge. |
| `event_store_engineer` | Retain event history/snapshot/recovery expertise. Compare transactional procedures with SQLite specialties. |
| `event_stream_engineer` | Retain stream batching/coalescing expertise. Share transport diagnostics where their ordering and scope contracts match. |
| `instruction_maintenance_engineer` | Strong instruction-reconciliation procedure candidate. Compare shared document maintenance with specification reconciliation. |
| `interactive_world_architect` | Retain world-format/scene-authority design expertise. Its planning method can be a skill without flattening the domain. |
| `keyboard_navigation_engineer` | Retain input/focus/navigation expertise. Reuse browser interaction testing procedures where applicable. |
| `mcp_integration_engineer` | Retain MCP extension/discovery/transport expertise. Compare harness/onboarding procedures, preserving protocol distinctions. |
| `memory_query_engineer` | Retain memory visibility/relation/receipt expertise. Compare SQL optimization methods with SQL projection, not automatic role equivalence. |
| `module_lifecycle_engineer` | Retain composition/provider/process ownership expertise. Common module-lifecycle procedures may serve other domain profiles. |
| `onboarding_engineer` | Startup/onboarding procedure candidate. Compare duties with context delivery and instruction maintenance against consent/recovery requirements. |
| `person_interaction_engineer` | Retain cross-surface correlated interaction expertise. Common consent/error analysis may be a skill. |
| `procedural_environment_engineer` | Retain environment/shader/editable-state expertise. Do not infer equivalence with character motion or world architecture. |
| `project_layer_engineer` | Retain storage/layer provenance expertise. Inventory/linking procedures are candidates for selective skills. |
| `python_environment_engineer` | Strong reproducible-environment procedure candidate. Preserve caller environment and cleanup requirements. |
| `python_packaging_engineer` | Packaging/scaffold procedure candidate with distribution expertise retained when needed. Compare checks with environment/quality roles. |
| `python_quality_engineer` | Strong focused quality-repair procedure candidate. Keep behavior and meaningful regression evidence distinct from blanket checks. |
| `spatial_ui_engineer` | Retain DOM/3D attachment and projection expertise. Share spatial diagnostic methods without merging rendering layers. |
| `specification_reconciliation_engineer` | Strong evidence-based document reconciliation procedure candidate. Compare with instruction maintenance, preserving source/spec authority distinctions. |
| `sql_projection_engineer` | Retain SQL projection/hydration expertise. Share query-planning procedures with memory/event store where contracts agree. |
| `sqlite_concurrency_engineer` | Retain transaction/locking expertise. Differentiate concurrency repair from query projection and migration. |
| `system_reliability_engineer` | Reliability-triage procedure candidate plus cross-owner coordination. Examine overlap with investigator/lifecycle work without inventing a permanent coordinator. |
| `web_authorization_engineer` | Retain access-boundary expertise. Do not merge with credential lifecycle merely because both involve security. |
| `web_credential_security_engineer` | Retain credential renewal/origin/identity expertise. Share security review procedures where appropriate. |
| `web_runtime_engineer` | Retain canonical in-process web/CLI integration expertise. Compare module/MCP integration methods while preserving caller attribution. |
| `web_settings_engineer` | Settings integration procedure candidate plus declaration/lifecycle expertise. Compare with web runtime against exact endpoint contracts. |
| `web_state_engineer` | Retain event-driven browser reconciliation expertise. Share invalidation procedures where independent view/DOM contracts agree. |
| `webgl_rendering_engineer` | Retain GPU depth/transparency/batching expertise. Rendering procedures can be skills, but performance and correctness need domain knowledge. |
| `work_board_engineer` | Retain persistent board/ticket identity expertise. Compare task-planning procedures with decomposer and dispatch orchestration. |

## What the native evidence does and does not price

The archived workload is three related label/sequence/render contributions on the same prepared runtime, with matching functional artifacts and acceptance checks. It excludes runtime selector/planner overhead. Each arm has three ACP work prompts. Original uses three native conversations. Later arms use one native conversation and two resumes, but still have **three execution proxy processes**. These counts directly show why conversation reuse and process reuse must be distinguished. [comparison JSON](acp-native-efficiency-comparison.json)

| Historical arm | Native conversations | Execution proxy processes | Native model responses | Uncached input |
| --- | ---: | ---: | ---: | ---: |
| Original `977f1bfe` | 3 | 3 | 96 | 179,010 |
| Prior `8df925ee` | 1 | 3 | 55 | 100,739 |
| A, gateway hint | 1 | 3 | 61 | 169,539 |
| B, pinned duty/guidance | 1 | 3 | 33 | 68,614 |
| C, explicit diagnostics/receipt correction | 1 | 3 | 45 | 87,998 |
| Final guide arm | 1 | 3 | 37 | 78,562 |

The samples do not isolate role-to-skill conversion. They do not price a Facilitator commission, the new mandatory usage-read path or universal regional context. B outperforms later arms, A regresses, and host skill-catalog injections vary. Do not describe the final guide branch as causally responsible for all savings: that native run did not invoke `metaform_instructions`. Dollar cost is unavailable. Hidden provider work and context retention are not disclosed. [measurement limits](acp-context-implementation.md#native-inference-follow-up-2026-10-23)

A same-context skill could avoid reorientation and communication work when the caller already has relevant understanding. It could also add library/procedure tokens, contaminate a requested independent assessment, displace useful context, increase sequential latency or forgo useful parallelism. A separate specialist may select a better runtime or contribute expertise the caller lacks. Which dominates is a workload-dependent hypothesis, not measured savings in this appendix.

### A skill cannot silently assume a commission or another assignment's ownership

The present integration is not changed by renaming a duty to `SKILL.md`. Loading or serving text does not change `assignments.authored_role_uri`, `gc_assignment_id`, `role_requests.creator_assignment_id`, the bound session or the recorded return destination. Direct checks relevant to an existing agent loading Facilitator guidance are:

- `_delegate` rejects a direct `facilitator` or `role_creator` contribution and points to the commission route. [state.py:1137](../../src/metaform/modules/orchestration/state.py#L1137)
- `commission` requires the requesting assignment to match the request's recorded delivery GC. [state.py:1320](../../src/metaform/modules/orchestration/state.py#L1320)
- `publish_role` requires the publishing assignment to be the request's recorded creator. Reading the corresponding persona or skill does not satisfy this predicate. [state.py:1339](../../src/metaform/modules/orchestration/state.py#L1339)
- Recording a full-model fallback runtime choice requires both a Facilitator/legacy URI and a matching commissioned request for that work. [state.py:399](../../src/metaform/modules/orchestration/state.py#L399)
- Team broadcast and interruption use recorded GC ownership. `owns` checks the sender assignment's own GC identity, the recipient's GC/team identity and distinct assignment identity. [dispatch orchestration:115](../../src/metaform/modules/dispatch/orchestration.py#L115), [state.py:727](../../src/metaform/modules/orchestration/state.py#L727)

These observations identify integration constraints for a proposal. They do not authorize removing the predicates, changing explicit user controls, or manufacturing an assignment identity from loaded instructions. Pro must decide how a proposed same-context method cooperates with the current responsible assignment and supported operations, and identify any concrete API change separately.

### Native children: blanket claim corrected, complete parity remains unproven

The prior person-facing system prompt prohibited native background subagents because Metaform supposedly could not see, steer or account for them. This preparation replaces that absolute claim with adapter-dependent observation, parent-mediated messaging and accountable work/results following user preferences. The correction is supported by existing code: the runner advertises native-subagent capability, observes spawn/state events, keeps child thread updates and can queue an exact person-addressed child message through its parent. [dispatch prompt:314](../../src/metaform/modules/dispatch/resources/prompts.xml#L314), [runner.py:1938](../../src/metaform/modules/dispatch/runner.py#L1938), [runner.py:2118](../../src/metaform/modules/dispatch/runner.py#L2118), [runner.py:2735](../../src/metaform/modules/dispatch/runner.py#L2735), [runner.py:4202](../../src/metaform/modules/dispatch/runner.py#L4202)

This establishes that some adapter-reported native children are observable and have a person-message delivery path. It does not establish support for every host's background tasks, per-child billed-cost accounting, stop/admission parity or managed assignment/return semantics. Parent-mediated child delivery is queued, not proof that the parent/native tool successfully reached the child. The corrected prompt does not claim full control parity. Pro should evaluate the remaining adapter-specific requirements before deciding future execution defaults; the preparation does not implement that redesign.

### Text composition measurements for the nine canonical skills

These are UTF-8 **text bytes**, not tokens, inference cost, live deployment bytes or a measurement of actual model delivery. The check uses a new temporary Metaform home with no user overrides, `skills.load(name)` and `skills.served(name)` without an input. It reflects the final corrected shipped skill/library authoring snapshot, also captured in [the byte record](context-management-skill-bytes.json). The combined SHA-256 of the ordered JSON inputs and rendered outputs is `9a87b6beec1803a3c3384a5936e2ce353cf9bdd6302df28589095d599f8199d8`. Later source edits may change the result.

| Skill | Authored SKILL.md | Authored procedure | Required libraries, rendered | Complete served body |
| --- | ---: | ---: | ---: | ---: |
| `import-workflow` | 711 | 10,559 | 24,080 | 34,645 |
| `prompt-efficiency` | 576 | 5,088 | 19,841 | 24,933 |
| `scan` | 395 | 3,073 | 0 | 3,073 |
| `sentinel` | 641 | 9,976 | 9,854 | 19,832 |
| `work-evidence` | 1,775 | 490 | 0 | 490 |
| `workflow-builder` | 619 | 5,258 | 24,080 | 29,344 |
| `workflow-efficiency` | 699 | 6,125 | 34,979 | 41,112 |
| `workflow-evaluator` | 623 | 4,027 | 24,080 | 28,113 |
| `write-workflow` | 697 | 17,678 | 24,080 | 41,764 |

Authored procedure length follows `skills.procedure`, which strips its surrounding whitespace. `served` does not include the SKILL.md file. Library totals sum the required library bodies once each for that skill; served totals also include the renderer's separators. Shared libraries recur in the output of separate full skill loads. The existing line/body receipt mechanisms do not imply that these full returned skill bodies are automatically deduplicated. This is a concrete reason to evaluate composition rather than assume a skill wrapper is smaller. [skills.py:73](../../src/metaform/skills.py#L73), [skills.py:109](../../src/metaform/skills.py#L109), [skills.py:126](../../src/metaform/skills.py#L126), [skills.py:138](../../src/metaform/skills.py#L138)

Reproduction after selecting the intended source snapshot, without touching a live Metaform home:

```python
import hashlib, json, os, tempfile
with tempfile.TemporaryDirectory(prefix="metaform-pro-skill-bytes-") as folder:
    os.environ["METAFORM_HOME"] = folder
    from metaform import skills
    payload = []
    for skill in skills.catalog():
        loaded = skills.load(skill.name)
        payload.append({"name": skill.name,
                        "frontmatter": (skill.folder / "SKILL.md").read_text(),
                        "procedure": skills.procedure(skill.name),
                        "libraries": loaded["libs"], "served": skills.served(skill.name)})
    print(hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                   separators=(",", ":")).encode()).hexdigest())
    for row in payload:
        print(row["name"], len(row["frontmatter"].encode()), len(row["procedure"].encode()),
              sum(len(body.encode()) for body in row["libraries"].values()),
              len(row["served"].encode()))
```

## Checks performed and open questions

Read-only source checks followed the parent graph audit, project `home-rich-metaform`, generation `2026-10-23T15:36:26Z`. Added graph searches returned seven exact installer/workflow/BMAD/skill symbols with complete pagination. Exact relevant source paths had no recorded coverage issues and `metadata_match`. Procedure `.axiom` paths reported untracked coverage, so those files were read directly. Two initially guessed module paths were absent, then corrected to `src/metaform/install.py` and `src/metaform/modules/orchestration/bmad.py` and checked. Coverage is a best-effort signal, not proof of source completeness.

An import/AST metadata check, with bytecode writing disabled, verified 23 authored duties, nine skills/seven discoverable, and no project-local BMAD discovery entries in this checkout. The frozen inventory's lengths and specialty-name uniqueness verify `6/23/39`. These reads did not invoke role resolution/publication against the live registry or launch an agent.

Three existing focused tests were run in isolated fixture homes, without native inference:

```text
uv run pytest -n 0 -q \
  src/metaform/modules/agents/tests/test_authored_roles.py::test_native_responsibility_inventory_and_selected_identity \
  src/metaform/modules/workflow/tests/test_workflow.py::test_cli_stored_call_fresh_handoff_frozen_text_and_return \
  src/metaform/modules/workflow/tests/test_skills.py::test_assignment_serves_each_lib_once_then_skill_then_input_and_closes
```

Initial diagnostic result before prompt/fixture corrections: **one passed, two failed in 5.47s**. The inventory/selected-role test passed. The workflow handoff test failed because its expected concrete resume command was replaced by handoff prose about a recorded continuation. The skill-assignment test's direct `workflow_resume` tool call failed after the new instruction prerequisite, without first reading the required guide. These are recorded limits of the current checks, not passing evidence of automatic dispatch integration. No source or fixture was edited by this read-only investigation. The continuation prompt owner subsequently restored the usable resume command and migrated the client to actual instruction reads; both cases pass in the final focused workflow checks recorded in the implementation report. The initial failures remain here as diagnostic provenance.

Questions for Pro:

1. Which responsibilities need distinct accountable results, independent judgment, runtime choice, concurrency or workspace isolation, and which are methods the current assigned agent can apply?
2. Should a procedure selected in the current assignment preserve the same assignment/source/return identity while composing instructions differently? Define the desired behavior before choosing a skill or persona format.
3. Which of the proposed overlap groups have genuinely equivalent duties and routes after reading complete selected duty text, rather than similar purpose names? What historical URIs, role snapshots, definitions and pending continuations must survive?
4. What exact host/caller route starts and binds the recipient of `workflow handoff`, `assign` and `parallel` today? If an integration is missing, treat it as a distinct execution problem. Do not claim text or a run record already supplies it.
5. How should raw `workflow skill` reads relate to selected procedure overrides? How will exact selected skill/library bodies be observable when supplied through MCP or native files?
6. What are the measured end-to-end costs of existing-specialty reuse, Facilitator selection, runtime-only commission, role creation and helper work, including the current usage prerequisites? Existing six-arm numbers do not answer that question.
7. Does moving a method into the same conversation reduce total native requests/input/output for matched useful work while preserving quality, user responsiveness, source fidelity and requested independence? A controlled comparison would need explicit authorization. It has not been run here.
8. Which existing Facilitator/GC predicates are part of a necessary recorded workflow contract, and what explicit supported operation would a same-context procedure use instead? Loading a skill does not activate those identities today.
9. Which reported native-child capabilities meet actual visibility, message delivery, cost, stop and assignment requirements for each adapter? The false blanket prompt explanation is corrected in this preparation. Establish the remaining parity and work-specific execution choices before designing a new default.
