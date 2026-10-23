# Current-context methods and Facilitator migration

Baseline: `879f2314f9eb7b11fa46efeffdd126cd04aef733`.
Branch: `context-management-pro-handoff-879f2314`.

## Implemented shape

An execution mode identifies where a contribution runs: current informed context, continued ACP episode, or separate execution. A responsibility identifies accountability. A skill supplies a procedure. A specialty supplies reusable domain expertise. An assignment identifies the actual requested contribution, its context, owner and return destination. Reading instructions is not launching or rebinding an agent.

`orchestration_methods` exposes four procedure families and the retained responsibilities. `orchestration_apply name=METHOD task=TEXT` loads selected instructions into the current context. An explicit `metaform://role/NAME` names a responsibility or specialty rather than a same-named native skill. Loading retains the existing assignment, execution role and authored-role identity. A local contribution is incorporated into that assignment rather than closing it through the supplementary method's return language.

Five native entries are shipped: `facilitator`, `shape-work`, `investigate-work`, `deliver-work`, and `evaluate-work`. The four families lead to individual methods only when needed. They do not each load every constituent duty. Specialist definitions remain in the dynamic registry behind Facilitator; the observed 39 names are not exported as 39 native skills.

The existing Facilitator has one selected duty, `prompt.orchestration:role_creator`, used by its native entry and existing role URI. The legacy `role_creator` URI remains compatible with saved assignments, not a second native skill or a required stage.

## Operational changes

| Operation | Behavior |
| --- | --- |
| `orchestration_facilitate op=find query=TEXT` | Rank specialist purpose metadata without loading bodies or excluding unmatched entries. |
| `orchestration_facilitate op=use role=NAME task=TEXT` | Read the selected expertise in the current context. No new assignment, process, model invocation or role rebinding is initiated by this operation. |
| `orchestration_facilitate op=publish role=NAME purpose=TEXT duty=TEXT` | Reuse an existing selected specialist or create missing expertise through the existing role registry and publication lock. Preserve caller identity and leave its work active. |
| `orchestration_runtime work=WORK choice=OBJECT` | Let the current informed caller supply a choice through the existing advertised catalog, override validation and runtime persistence. A separate Facilitator assignment is no longer required by this public operation. |
| `orchestration_claim`, `delegate`, `call`, `handoff` | Continue to assign actual execution through existing lifecycle, dependency, capacity and user-control mechanisms. |

Publication and runtime writes retain the configured dynamic blacklist check. Loading a skill supplies no new authority. Registry publication uses actual caller session and assignment provenance rather than impersonating a commissioned Facilitator. Existing selected duties are reused rather than overwritten by a new creation attempt. Explicit editing remains the existing versioned role/prompt editing operation.

A previously recorded execution commission still uses `orchestration_publish_role request=...`; this both binds its original contribution and completes that authoring assignment. The new registry-only publication does neither. This distinction prevents an inline procedure from finishing the implementation ticket merely because it created expertise. Existing pending commissions are not silently stolen or marked complete. Registry change events remain active and may unblock previously requested work; definition creation does not itself commission a new worker.

Headless routing can still commission a separate agent when there is no current informed executor. Explicit delegation of missing expertise also retains its legacy durable commission path. Current-context callers can find/create expertise before requesting execution instead of traversing that path. This change does not pretend that every existing autonomous call site has ceased creating commissions.

## Responsibility disposition: all 23

Existing source identities and role URLs remain addressable for historical assignments, selected edits and explicit separate execution. Procedure grouping changes discovery and recommended use, not the meaning of a stored assignment.

| Authored responsibility | Disposition and reason |
| --- | --- |
| triage | Retain user-facing responsibility. Conversation continuity and overall intent are not a generic reusable execution skill. Existing dispatch-owned source remains selected there. |
| gc | Retain delivery ownership; apply local methods and expertise, delegating useful contributions rather than each procedural step. |
| functionality | Retain independent functional assessment and adaptive publication; share assessment method while preserving canonical reviewed-work reopening. |
| harsh_critic | Retain requested independent verdict; share assessment method, preserve its distinct dependency-linked corrective-ticket return contract. |
| roundtable_follow_through | Retain existing stage/continuation responsibility and explicit user-directed stage reviews. The roundtables-owned source is not replaced by a generic method. |
| facilitator | One discoverable expertise method, usable locally or in an explicitly assigned contribution. Existing board delivery contract retained. |
| role_creator | Retain as historical alias to the same Facilitator duty; no separate native entry. |
| interviewer | `shape-work` method for guided idea development, selected when that contribution is needed. |
| requirements | `shape-work` method for source intent and referents; distinguishes user requirements from research and recommendations. |
| architect | `shape-work` method for build design and interface contracts. |
| designer | `shape-work` method for user journeys and interaction states. |
| planner | `shape-work` method for the requested written plan. Local approach development does not automatically launch Planner. |
| decomposer | `shape-work` method for a fresh project board and actual `after_work` dependencies. Duplicate ticket-writing sections consolidated. |
| investigator | `investigate-work` method for tracing behavior and cause. |
| researcher | `investigate-work` method for sourced technical investigation; requirements formalization uses the existing requirements method rather than another copied procedure. |
| synthesizer | `investigate-work` method for integrating evidence and preserving disagreement. |
| specialist | Shared execution/return duty within `deliver-work`; domain definitions supply the expertise. |
| implementer | `deliver-work` implementation method composed with the shared Specialist duty rather than another copied execution contract. |
| integrator | `deliver-work` method for candidate integration and interactions. |
| release | `deliver-work` method for assigned release preparation; publication follows the existing explicit request. |
| verifier | `evaluate-work` method for outcome evidence. A local use is not described as an independent assessment. |
| reviewer | `evaluate-work` method for supported findings and requirement coverage. |
| dogfood | `evaluate-work` method for the actual user journey. Separate execution remains available for requested independence. |

The 16 procedural responsibilities are not 16 new native skill entries. They remain individually selectable methods within four families. Functionality and Harsh Critic share criteria but not correction semantics. Their different result handlers make collapsing their identities incorrect.

## Specialty disposition: all 39 observed definitions

Each definition was examined from the supplied current-duty corpus. All become usable as on-demand expertise through the same current-context operation, while remaining assignable for useful separate execution. No automatic merge of selected user-authored bodies is performed. Similar labels alone are not enough to erase different technical methods or historical source identities. Shared lifecycle/reporting guidance stays in the common and Specialist components; the revised Facilitator authoring method tells new definitions to supply domain methods, not copy those instructions.

| Observed specialty | Retained technical contribution; grouping rationale |
| --- | --- |
| agent_communication_engineer | Agent-message routing and correlated returns; distinct from session supervision. |
| agent_harness_integration_engineer | Native harness/adapter boundaries and capability behavior. |
| async_event_worker_engineer | Dedicated worker ownership for unavoidable upstream polling and cancellation. |
| async_transport_engineer | Byte streams, buffering, pipe EOF and resource cleanup; not interchangeable with event scheduling. |
| browser_performance_engineer | Browser computation complexity and allocation costs. |
| cache_invalidation_engineer | Source dependency/invalidation correctness, distinct from general profiling. |
| character_motion_engineer | Procedural motion and characteristic locomotion. |
| context_delivery_engineer | Selected instructions, grounding and delivery receipts. |
| data_migration_engineer | Persisted record movement, compatibility and atomic migration. |
| dispatch_lifecycle_engineer | Admission, supervision, stops and assignment-state transitions. |
| dispatch_orchestration_engineer | Coordinated work, dependencies and durable results; related to lifecycle but a different contribution. |
| embedded_engine_module_engineer | Packaging and lifecycle of an embedded engine with module integration. |
| event_store_engineer | Authoritative operation history and rebuildable snapshots. |
| event_stream_engineer | Stream deadlines, fairness and lossless coalescing. |
| instruction_maintenance_engineer | Native/repository guidance and operative instruction sources. |
| interactive_world_architect | Renderer-independent world design and shared human/agent operations. |
| keyboard_navigation_engineer | Physical keys, logical navigation, orientation and focus. |
| mcp_integration_engineer | Provider contracts, discovery and transport consumers. |
| memory_query_engineer | Selective graph retrieval and functional memory materialization. |
| module_lifecycle_engineer | Provider composition, enable/disable and resource ownership. |
| onboarding_engineer | First-run guidance, intake and recovery. |
| person_interaction_engineer | Cross-surface notices, decisions and event-correlated responses. |
| procedural_environment_engineer | Parametric geometry, surface metrics and canonical scene parameters. |
| project_layer_engineer | Knowledge placement, layer selection and references without moving source bodies. |
| python_environment_engineer | Interpreter/dependency isolation and evidence environment. |
| python_packaging_engineer | Distribution contents and installed resource parity. |
| python_quality_engineer | Lint/CI diagnosis and meaningful regression coverage. |
| spatial_ui_engineer | Camera transforms and visible attachment geometry. |
| specification_reconciliation_engineer | Requirement/source correspondence and document maintenance. |
| sql_projection_engineer | Paged reads, child hydration and consumer contracts. |
| sqlite_concurrency_engineer | Lock holders, transaction duration and atomicity. |
| system_reliability_engineer | Cross-system diagnosis and repair at the actual owner. |
| web_authorization_engineer | Existing HTTP/browser authority consistency; domain security work is not an agent capability policy. |
| web_credential_security_engineer | Browser credential issuance, renewal and restart behavior. |
| web_runtime_engineer | Canonical in-process operations replacing unnecessary CLI bridges. |
| web_settings_engineer | Setting declarations, effective scope and endpoint behavior. |
| web_state_engineer | Incremental browser state and stable DOM reconciliation. |
| webgl_rendering_engineer | Depth, transparency, atlases and GPU evidence. |
| work_board_engineer | Persistent board organization, ticket identity and history. |

These 39 are an observed inventory, not a hardcoded runtime catalog or a blacklist. Registry additions remain discoverable without changing the family map. Their saved source bodies and selected edits are retained. This source change does not rewrite live private-home role definitions or delete historical definitions.

## Source selection and context

`orchestration_apply` resolves selected skill procedures through the existing prompt store. For its current assigned role, it uses the assignment snapshot. Supplemental methods preserve that snapshot's common and Specialist components rather than silently replacing the active shared instructions. Other method bodies come from their current selected source. Source/version/fallback metadata travels with the exact delivered text.

The existing content ledger prepares due components. At the MCP boundary, complete body strings are queued for acknowledgment only if they survive response shaping. CLI returns record their complete output. A procedure lookup or native deployment does not establish an agent receipt. Accepted unchanged bodies are shared across method and library reads within the epoch. Actual compaction still owns epoch transitions; no retained-context proof, new model probe or universal system-prompt override is introduced.

`skills.components` supplies exact selected procedures and required library components. The `orchestration_apply` route deduplicates those components with role delivery. Existing explicit `metaform_skills load` and native deployment still provide complete artifacts; this does not claim they now have identical transport acknowledgment behavior. Existing library and immutable-definition bodies remain unchanged. The new method families require no automatic Axiom grammar/library payload.

Shipped orchestration text was consolidated at existing keys. Selected user edits and already pinned histories retain their current versioned behavior. The native installer uses the normal discovery/deployment mechanism; this checkout operation does not modify installed native files on the user's machine. Neither deployed prompt selection nor native reception was measured here.

## Verification actually performed

The candidate Python sources compile and the orchestration XML parses. The 16 tests in `src/metaform/modules/orchestration/tests/test_current_methods.py` passed in an offline Python/pytest harness that imports the actual new modules and substitutes unavailable repository services at their boundaries. They cover preparation versus accepted delivery, unchanged-body and epoch behavior, CLI acknowledgment, pinned role/source use, current identity, selected skill use, URI/name collision, missing-source errors, registry reuse without overwriting edits, actual caller provenance, dynamic blacklist checks, metadata ranking, runtime choices/overrides and invalid-choice reporting, all-23 family coverage, and native selected-artifact construction.

The tests use controlled receipt/catalog/transport services. They do not establish the production database transaction behavior, MCP serialization, native model context, end-to-end ACP execution, billed tokens or inference savings. Existing history/compaction implementations were reused, not independently certified by these unit checks.

A full clone could not be obtained in this environment. A temporary source-export workflow was created, failed before any job steps executed, and was removed; its add/remove commits have no net implementation content. Repository access and final changes use the authenticated GitHub connector. Full repository pytest, Ruff, Pyright, installed-native discovery and live ACP scenarios were not run. Prior handoff measurements are prior evidence, not measurements of this candidate.

The controlled harness is retained at `scripts/check_current_methods_offline.py` and runs with Python, pytest and PyYAML. It deliberately uses `--noconftest` and substituted service modules; it is not a substitute for the full-checkout command below. Run it with `python scripts/check_current_methods_offline.py`.

Reproducible focused command in a complete checkout:

```sh
uv run pytest -n 0 src/metaform/modules/orchestration/tests/test_current_methods.py
```

This is an implemented source-level continuation with bounded verification, not a claim of complete release validation. In particular, autonomous legacy commission routes and the two module-owned conversation/stage duties retain their existing execution contracts, and arbitrary user-edited specialty text has not been forcibly migrated.
