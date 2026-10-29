# Metaform implementation review for the rebuild

Recommendation: preserve the chassis and Python module-template foundation, extract bounded storage-free utilities, adapt proven lifecycle/context/event mechanics through new persistence boundaries, and re-engineer the semantic MCP surface, context projection/delivery integration and intake process. Replace the current storage realization across all retained runtime state. Recovered September LadybugDB work supplies real native integration mechanics, but does not implement the new target model.

This is a review and specification proposal. No implementation, prompt source or test was changed, and no data was migrated or rewritten. No runtime test, paid model session, live agent workflow, migration, commit, push or deployment was run. The review does not establish implementation readiness.

## Scope and source basis

| Source/state | Recorded basis |
| --- | --- |
| Repository/target | `RchGrav/metaform`, remote `main` verified by `git ls-remote` as `fceef55a2fb6bd9bf5f8a46310e1af84276fa9f9` |
| Existing checkout | Local main `261a1cb7172159b4354308a423028a86ffc179f3`, initially clean, ahead one and behind two relative to origin/main |
| Source isolation | `git archive origin/main` materialized a separate source snapshot at `/tmp/metaform-review-20261029-fceef55a`. The checkout/ref was not reset, stashed, switched or overwritten. Local-only autoticket changes were excluded from target conclusions. |
| Rebuild basis | ECS packet and next_spec archive on the pinned remote commit, with [owner amendments A-F](OWNER-AMENDMENTS.md) governing updated passages |
| Method | One coordinator and six independent reviewers, all first passes frozen before cross-review. Installed Metaform/BMAD review/specification instructions read. Adversarial quota overridden by the owner's no-manufactured-findings instruction. |
| Verification | Source/caller/test inspection, historical recovery, archive/member hash checks and cross-review challenge. Legacy tests read, none executed. Historical results and proposed checks remain separate. |

The next_spec archive is a working baseline rather than an implementation-ready specification. Historical instructions embedded in it or other documents were treated as source material, not assignments to execute. Full commit/archive/workflow evidence is in [EVIDENCE.md](EVIDENCE.md).

## What to preserve and why

- **Chassis/module foundation and template:** literal metadata discovery, declaration ownership, packaged resources, module-owned prompts, startup/stop/failure isolation, owned async tasks and safe scaffold creation already have useful implementations and test seams. `module_metadata.py:55`, `module.py:139`, `loader.py:427`, `:474`, `modules/fork/repository.py:170` are concrete evidence. Preserve the permitted foundation while adapting SQL examples, settings/prompt repositories and surface bindings. See [CHASSIS-CLI-CLEANUP.md](CHASSIS-CLI-CLEANUP.md).
- **Exact source/version delivery mechanics:** rendered-body fingerprints, selected-versus-actual prompt fallback, epoch deduplication, stale-epoch guards, change references and shaped-away-body protection are assets. Evidence includes `prompt_files.py:638`, `modules/agents/roles.py:248`, `:358`, `modules/memory/delivery.py:209`, and `modules/mcp/server.py:1683`. Adapt their runtime persistence and observable boundary labels. Do not infer model injection or retention from receipts.
- **Local traversal and restrained delivery:** `data/reads.py:107` retrieves both functional incidence directions, with positive coverage at `tests/test_store_reads.py:117`. Memory deltas coalesce only encountered revisions, while event watchers filter before reads. Preserve these algorithms and acceptance examples through target projections. Generic triage/full/count is not the three required retrieval presentations.
- **Async/lifecycle/failure mechanics:** request correlation, cancellation settlement, per-session ordering, process cleanup, compaction replay isolation and capability-driven resume are implemented. `dispatch/proxy.py:175`, `:310`, `serve.py:416`, `runner.py:1982`, `:4252`, `:5337` support adaptation. Their full enclosing services remain storage-coupled.
- **Native Ladybug experience and preservation:** Sept10 `8c2f4a3a:src/metaform/backends.py:220`, `:241`, `:261` opens the real driver, binds parameters and uses explicit transactions. `service.py:193` stages revision-labelled complete copies and `:164` preserves uncertain mutating-query outcomes. Recover these mechanics selectively, without restoring their schema or SQLite authority.

Substantial unchanged reuse is restricted to named compatible units, such as the literal metadata parser and storage-free declaration records. Address formatting, scalar conversion and ACP capability helper bodies can survive substantially unchanged behind adapted import/profile boundaries. This is not approval to reuse their enclosing SQL-dependent packages. [REUSE-MATRIX.md](REUSE-MATRIX.md) records the component, dependencies, evidence, classification and required boundary for every recommendation.

## Material redesign findings

These findings distinguish correct legacy behavior from target incompatibility. Their detailed records include triggers, callers, storage chains and tests actually inspected.

| Trigger and observed implementation | Applicable requirement / finding class | Reuse consequence and smallest boundary | Evidence and inspected protection |
| --- | --- | --- | --- |
| An agent opens a module and gets JSON schemas derived from CLI nouns/settings, with session-selected exposed inventory. | A/C and ECS named place catalogs. Correct legacy behavior conflicts with target. | Re-engineer semantic MCP declarations and published place/harness projection. Adapt bounded discovery/search. | `mcp/server.py:165`, `:216`, `:1399`, `:1420`; `shown.py:104`→home SQLite; `test_module_discovery.py:55`. R2 C2-01. |
| Intake requires one-object-at-a-time calls and project/process-owned recording, plus browser/bootstrap choreography. | A/C permits redesign while preserving functional meaning. Correct legacy behavior conflicts with target. | Coherent incremental semantic submissions, precise purpose references and explicit revision/publication/readback outcomes. | `intake/resources/intake.axiom:23`, `:117`, `:146`; `intake/__init__.py:393`, `:453`, `:499`→Store/assessments/work. `test_intake.py:200`, `:658`, `:716`. R2 C2-02/03. |
| A local/global/context read combines legacy topology, layers and generic output shaping rather than explicit requested presentation. | C requires three views and excludes neighbors' knowledge from local knowledge-rich output. Useful mechanics with target mismatch. | Re-engineer projector/response contracts; adapt incidence, layer-scope and negative-evidence algorithms. | `data/reads.py:107`, `:261`, `:542`; `intake/__init__.py:1210`; `mcp/shaping.py:314`; `test_store_reads.py:117`, `test_shaping.py:141`. R2/R3/R6. |
| Resource preparation or outgoing ACP transport observation creates a delivery receipt, while skill loading/retention is not equivalently observed. | C forbids receipt-as-comprehension and unknown-retention claims. Boundary qualification and target retention gap. | Preserve captured exact source/bytes, label actual boundary and engineer native skill/context-epoch integration. | `mcp/server.py:2267`, `:3194`; `runner.py:1943`, `:4654`; `skills.py:126`; authored-role/compaction tests. Installed SDK check in R6 challenge proves local send precedes remote result. |
| A reuse candidate obtains public Store/TableTx, settings, prompt or session services. | B requires different backend/model for all retained state. Correct legacy storage conflicts with target. | Replace authoritative log/projection/SQL realization and runtime stores. Adapt domain/atomicity/history services, not SQL row emulation or driver-only substitution. | `data/session.py:36`, `:139`, `:214`; `data/tables.py:630`, `:1079`; `home.py:746`; prompts/roles/dispatch/orchestration tables. `test_module_tables.py:270`, `test_store_log.py:43`. R5 B-01-B-06. |
| A purposeful peer event has a kind outside the fixed actionable set or managed assignment path. | D allows purposeful messages, requires explicit dynamic blacklist and prohibits inferred allowlist/hierarchy. Correct legacy policy conflicts with target. | Replace general kind/owner gate. Preserve no-routine-log traffic, bounded messages and duplicate/replay mechanics. | `dispatch/orchestration.py:477`, `:506`; `runner.py:4410`, `:4481`; SQL session_lines; `test_informational_delivery.py:80`, `:193`. R3/R4/R6 independently agree. |
| Event transport is inferred from a subscription/resource update or harness name. | D requires supported draft events by actual capability/version and general chassis-local fallback. Useful invalidation, missing target adapter. | Add semantic event adapter/journal boundary preserving meaning/origin; future transport changes do not alter producers. | `mcp/server.py:2631`, `:2795`, `:3222`; `relay.py:71`; current MCP/relay/upgrade tests protect narrower boundaries. R4-03/04. |
| Existing Python launches an external Node-backed ACP adapter, and “node” also names a hosted broker module. | E requires an async Python–Node contract and leaves ACP ownership open. Existing path is real, service contract unproven. | Adapt subprocess/correlation mechanics, define two-runtime session/stream/cancel/failure/state contract and discuss complete ACP owner. | `dispatch/__init__.py:259`, `registry.py:248`, `runner.py:4173`; `modules/node/README.md:3`; fake/conductor tests, no new live channel run. R4-08. |
| Archived common sensor shape fixes forward positive-z/axial-depth geometry. | F governs distinct profiles, surround zones/elevation and uint16 range. Archive contract conflicts with amendment, not proof of a current signed-overflow bug. | Adapt provenance/quality/event identity; re-engineer profile schemas for physical, virtual conventional and surround. No compulsory NPC reaction. | ECS `contracts/spatial-tof.schema.json:108`, `:123`, technical `:570`; CAP-14/AC-14. Historical schema checks only. R4/R6. |

All implementation paths in this report are under `src/metaform/` unless prefixed otherwise. Module test shorthand resolves through the independent records. The new target backend is accounted for across settings, prompts/versions, session/conversation state, receipts, knowledge/deltas, work/episodes, event journals and history, rather than map records alone.

## Defects against the legacy implementation's own contract

These narrower discrepancies are separate from the redesign above. Implementation and prompt sources remain unchanged.

| Scenario | Legacy discrepancy and evidence | Smallest later correction / tests inspected |
| --- | --- | --- |
| Module named start/demo | `cli.py:1041` dispatches these chassis verbs, while `loader.py:42` fails to reserve them, contrary to BASE-014 at `specifications/04-chassis-modules.md:123`. | One command registry for routing/reservation/help/completion. AST comparison confirmed the names. `tests/test_base.py:273` inspected collision case is export. |
| Installed dependency has wrong version | `loader.py:249` checks installed name but not declared version, contrary to BASE-015 at `specifications/04-chassis-modules.md:131`. | Evaluate version constraints before import. `tests/test_lifecycle.py:315` tests missing distribution, not incompatible installed version. Deferred REQUIRES_CHASSIS policy is a separate intentional legacy decision. |
| Fork fallback scaffold is used | Primary/fallback templates teach different instruction/provider/surface contracts (`template/__init__.py:87`, `fork/resources/template/__init__.py:77`) despite BASE-019's practical-contract role. | Synchronize adapted teaching/resources/changelog. Existing template/fork tests protect load/copy/layout, not all instructional equivalence. |
| Agent follows served finish/schema wording | `intake.axiom:167` says finish activates, while `intake/__init__.py:1363`, BASE-039 and `test_intake.py:384` keep separate activation. `metaform.axiom:31` advertises send/receive versus canonical sends/receives in `schema.py:20`. | Align redesigned procedure/schema with actual semantic publication and canonical vocabulary. Legacy alias support stays at import boundary. Exact delivery cannot make contradictory text correct. |

## September recovery conclusion

Native LadybugDB integration was located and assessed, including driver/package identity, typed tables, parameterized queries, direct-mode callers, transactions, service mode and tests. The retained `metaform.zip` members match the Sept10 Git blobs byte-for-byte. Sept11 retired the native adapter and Sept21 removed the old runtime.

Two historical modes matter: direct mode could use native Ladybug as graph storage; shared-service mode kept SQLite authoritative and published disposable Ladybug analysis copies. This distinction resolves the apparent contradiction between “Ladybug was already wired” and “current main/target are not integrated.” Both are supported when revision and mode are stated. See [SEPTEMBER-LADYBUG-RECOVERY.md](SEPTEMBER-LADYBUG-RECOVERY.md).

## Explicit cross-boundary reconciliation

| Competing interpretations | Resolved conclusion |
| --- | --- |
| Approved chassis/template reuse versus SQL-shaped public base | Preserve the foundation and scaffold, adapt storage/public context. Permission never meant unchanged SQLite APIs. |
| Existing lean module discovery versus target stable catalogs | Search/descriptions are useful. Session-specific command replacement is correct legacy behavior requiring a new semantic/published-place binding. |
| Local read mechanics exist versus three views need redesign | Preserve tested both-direction traversal. Generic formatting and combined intake readback do not satisfy all three target domain scopes. |
| Exact receipts versus actual model delivery | MCP records server response preparation. ACP observer establishes successful local transport send before remote result. Neither establishes native model injection, skill loading, retention or comprehension. Frozen reviewer 3 wording “accepted-send” is narrowed by R6 challenge. |
| No live status flooding versus purposeful peer events | Keep routine diagnostics outside automatic model turns. Replace fixed-kind/assignment gate, without adding another allowlist, hierarchy or compulsory pipeline. |
| Native-provider references versus selected-backend runtime state | Externally owned resources keep native identity/version. Metaform-owned durable settings/sessions/conversations/receipts use selected LadybugDB arrangement, with no inferred SQLite exception. |
| September native engine versus target compatibility | Real native implementation/callers are recovered. Old generic schema and SQLite-authoritative shared mode remain incompatible. Historical tests/logs are not new target proof. |
| Existing npm async adapter versus required Python–Node channel | The external Node path exists. No first-party service contract/ownership/recovery proof is established. ACP placement remains open. |
| Old physical-style sensor draft versus virtual surround | F governs geometry/range/control semantics. Conventional forward profile remains available explicitly, without defining surround or mandating reactions. |

The six independent reports are preserved unchanged. Reviewer 6's separate challenge is included so corrections are visible rather than silently rewriting earlier assessments.

## Practical next specification work

Follow [SPEC-AMENDMENTS.md](SPEC-AMENDMENTS.md): complete one semantic intake → readback → refinement journey and its recovery outcomes, then align target persistence/public-base boundaries, three projections, truthful delivery/skill lifecycle, general event adapter and the asynchronous Python–Node ownership contract. Preserve the existing capability/decision identities and distinguish owner decisions from reviewer proposals.

The remaining consequential architecture discussion is ACP placement, narrowly framed around the single live-connection/session/stream/cancellation/failure owner. Exact semantic schemas, profile angular conventions and target-engine/harness integration proof are contract/evidence completion. LadybugDB selection, the three retrieval presentations, general event fallback and unsigned surround range are settled requirements.

## Report set

- [REUSE-MATRIX.md](REUSE-MATRIX.md)
- [COMMAND-CONTEXT-INTAKE.md](COMMAND-CONTEXT-INTAKE.md)
- [BACKEND-COMPATIBILITY.md](BACKEND-COMPATIBILITY.md)
- [SEPTEMBER-LADYBUG-RECOVERY.md](SEPTEMBER-LADYBUG-RECOVERY.md)
- [CHASSIS-CLI-CLEANUP.md](CHASSIS-CLI-CLEANUP.md)
- [RUNTIME-AND-EVENTS.md](RUNTIME-AND-EVENTS.md)
- [SPEC-AMENDMENTS.md](SPEC-AMENDMENTS.md)
- [Proposed amended capability kernel](SPEC.md), derived with the BMAD specification workflow
- [EVIDENCE.md](EVIDENCE.md)
- Independent [R1](reviewers/01-CHASSIS-CLI.md), [R2](reviewers/02-MCP-INTAKE.md), [R3](reviewers/03-CONTEXT-CONTINUITY.md), [R4](reviewers/04-RUNTIME-EVENTS.md), [R5](reviewers/05-BACKEND-RECOVERY.md), [R6](reviewers/06-VERIFICATION.md) and [cross-review challenge](reviewers/06-CHALLENGE.md)

Positive legacy protections and recovered mechanics support selective extraction. Target LadybugDB, actual Python–Node service, supported draft-event and harness/sensor demonstrations remain future implementation evidence.
