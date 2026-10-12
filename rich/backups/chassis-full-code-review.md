# Metaform chassis — code and state review

**Reviewed snapshot:** `chassis-2026-09-18-020056Z`  
**Captured branch:** `realignment-2026-09-10`  
**Captured HEAD:** `ff6d53f5533d071612ceb574a94338efdffa3af9`  
**Review date:** 2026-09-18  
**Mode:** read-only review; no source files in the snapshot were modified.

## 1. Executive assessment

The fresh chassis is a real, cohesive implementation rather than a documentation shell. Its plugin lifecycle, contextual CLI, settings/glue, project-scoped records and provenance, durable assignments, shared runtime, async jobs, events, cancellation behavior, module discovery, example modules, and executable-wheel path are all implemented and substantially exercised.

The primary risk is **state and transition**, not the basic chassis mechanics. Most of the fresh chassis implementation exists as untracked working-tree content rather than in the captured Git HEAD, while a much larger legacy Metaform implementation remains beside it. The fresh chassis documentation correctly says intake, workflow execution, graph layers, MCP, and complete origin/variant reconstruction are not yet migrated. The repository root README does not consistently reflect that boundary.

The most important semantic issue for the next migration is concrete: the legacy intake conversion still models **one EF per Element**, while the current Canonical Intake requires the **PE's encounter-specific EF to be stored in the RE-owned join**. That old code must not be treated as the implementation contract for the new intake.

## 2. What was reviewed

The archive contains 245 captured source files. The manifest classifies them as:

| Category | Files |
| --- | ---: |
| Existing package/supporting code | 158 |
| Documentation/design context | 31 |
| Fresh chassis runtime | 20 |
| Example plugins | 16 |
| Focused verification | 13 |
| Build/entrypoint | 6 |
| Existing built artifact | 1 |

The Python package contains roughly 24.2k lines across the combined fresh and older implementation. The identified fresh-chassis slice is roughly 4.1k lines across its 20 runtime files.

The review covered the fresh runtime and its integration boundary, including:

- plugin contract and discovery/activation/deactivation;
- service context and public service facades;
- SQLite records, settings, jobs, events, assignments, and provenance;
- contextual CLI and working-directory/module/nonce navigation;
- shared runtime host/client and sync/async execution;
- cancellation/finalization behavior;
- event dispatch and retained delivery records;
- settings, pins/glue, and TUI;
- example `showcase`, `event_requester`, `harness_runner`, and web modules;
- packaging and executable-wheel entrypoint;
- focused chassis tests and verification records;
- current legacy intake/coarse conversion versus the new `Canonical_Intake.xml`.

## 3. Repository and delivery state

The captured workspace was not clean:

- **170** captured files were unchanged relative to HEAD.
- **13** were modified relative to HEAD.
- **62** were untracked.

Of the 20 files classified as fresh chassis runtime, **18 were untracked**; `src/metaform/cli.py` and `src/metaform/modules/__init__.py` were modified tracked files. The focused tests, current chassis API docs, example modules, and wheel are also largely represented by working-tree/untracked material.

This means the reviewed product is faithfully preserved by the archive, but **HEAD alone does not reconstruct the reviewed chassis**. A normal patch generated from tracked changes would also omit the untracked implementation.

The archive verification itself is internally strong: all 245 captured source files matched their recorded original SHA-256 hashes, and the preserved wheel matched its recorded SHA-256.

### Wheel/source correspondence

The preserved wheel is:

`dist/chassis-product/metaform_chassis-0.2.0-py3-none-any.whl`

SHA-256:

`27c5489657c7df67e21fcc81e021ba8b2e9146561dba3e5f595a4715ca12b27d`

The archive conservatively did not assert that this wheel corresponds to the captured source. I compared the package directly: **all 178 `metaform/*` files packaged in the wheel match the captured source byte-for-byte**. No packaged `metaform/*` file differed.

So the historical wheel verification is relevant to this exact captured package source, not merely to an earlier similar tree.

## 4. Fresh chassis architecture observed in code

### Plugin boundary

`src/metaform/plugin_contract.py` defines a small live Python contract:

- `Plugin`
- `Setting`
- `Subscription`
- module operations;
- complete Click commands;
- start/stop hooks;
- command and operation visibility callbacks;
- embedded help.

The chassis reserves its own command names and rejects collisions. Plugins can be individual `.py` files or packages. The authoritative disabled policy is a plain-text `plugins/disabled` file, and disabled plugins are skipped before import.

### Invocation context and services

`src/metaform/service_context.py` uses a `ContextVar` containing `WorkContext(project, nonce, producer, module, working_dir)`. The public services resolve through that invocation-local binding instead of constructing independent databases or runtimes at import time.

This is a good fit for the required interleaving of multiple project/assignment contexts across the same host.

### Data and provenance

The fresh store uses one SQLite database per configured global root. Records are project-scoped and revisioned. Writes require a producer, and public typed objects preserve record, producer, assignment, job, and module meaning across transport serialization.

The current provenance implementation is smaller than the whole eventual Metaform provenance model, but within the chassis slice it is concrete rather than an unrelated activity log.

### Assignments

`src/metaform/assignments.py` maintains durable assignment records, submissions, and tracked processes. Assignment delivery uses a nonce and exact submission header. Finalization commits durable state before clearing local discovery/navigation markers.

The tests exercise missing-header rejection, interleaved assignments, cleanup, and completion races.

### Shared runtime

`runtime_client.py` and `runtime_server.py` implement a persistent host per global root with local authenticated RPC. On Unix the runtime uses a protected Unix socket; on Windows it uses loopback TCP. Host metadata and token material are protected locally.

The runtime keeps jobs alive after the initiating CLI process exits, supports sync and async plugin work, retains job outcomes, and records cancellation/interruption honestly.

### Contextual CLI

The active `metaform` entrypoint now routes through the fresh contextual CLI. Module entry replaces the base surface and persists through a hidden working-folder binding; assignment context exposes the assigned-work surface. `exit` detaches navigation, while completion/abort settle durable work.

The old command surface remains separately available through `python -m metaform.legacy_cli`.

### Settings and TUI

Module Python owns setting definitions, defaults, types, and help. Glue/pins preserve user baselines across resets and unload/reload. The BIOS-style terminal setup surface is implemented over those same declarations rather than a second hardcoded settings catalog.

### Events

Events use the same runtime for sync and async subscribers. Delivery records are attributable to the publishing and subscribing operations/modules, and one subscriber failure does not suppress unrelated handlers. The event bus remains notification infrastructure; explicit workflow progression is not hidden inside it.

## 5. Verification performed during this review

### Static/executable checks

`python -m compileall -q src/metaform examples/plugins tests` completed successfully on the captured tree.

### Focused test rerun

The archive records **86 focused tests passing** on Linux/Python 3.13.5. I independently reran the captured source using the wheel's bundled dependencies where the surrounding environment lacked packages.

The following groups completed successfully:

| Test group | Passed |
| --- | ---: |
| chassis CLI slice | 7 |
| chassis menu product | 6 |
| chassis services | 2 |
| chassis jobs | 18 |
| setting/glue | 4 |
| plugin runtime slice | 11 |
| chassis TUI | 4 |
| demo templates | 8 |
| shared runtime | 14 |
| web plugin slice | 4 |
| plugin discovery | 7 |
| **Directly rerun total** | **85** |

The one-test `test_chassis_walkthrough.py` exceeded this execution environment's command ceiling rather than producing a failing assertion. I then reproduced its acceptance journey manually in smaller command groups against the same captured source. That journey successfully demonstrated:

- load of `showcase`, `harness_runner`, and `event_requester`;
- shared persistent host operation;
- record creation/revision;
- setting-based command visibility;
- asynchronous job completion and cancellation;
- nonblocking event requester → harness fixture → completion event;
- missing-header rejection and headed assignment submission;
- completion and marker cleanup;
- module unload without breaking another module;
- direct harness work and assignment finalization;
- module reload with retained setting value;
- clean runtime shutdown.

Therefore I found no behavioral contradiction with the recorded 86-test verification. The distinction is that 85 test cases were rerun as pytest cases here; the 86th scenario was reproduced manually rather than completed by pytest within the tool ceiling.

I did **not** rerun the entire older Metaform package's historical test universe. The verification above is specifically the focused fresh-chassis suite and its acceptance journey.

## 6. Findings

| ID | Severity | Finding | Evidence / consequence |
| --- | --- | --- | --- |
| F1 | High | **Legacy intake stores EF on Elements, incompatible with the current Canonical Intake.** | `src/metaform/coarse.py:1-6,52-80` explicitly defines notable Elements “with one EF each,” requires `element["ef"]`, and joins contain purpose but no EF. `src/metaform/answers.py:95-128,141-165` likewise parses/stores element EF and drops join-local EF. The current canonical prompt explicitly forbids element-level EF records and stores each PE's encounter-specific EF in the RE-owned join. These legacy files are not yet part of the fresh chassis migration, so this is a transition hazard rather than a current fresh-chassis runtime failure. |
| F2 | High | **The reviewed fresh chassis is mostly outside Git HEAD.** | 18/20 fresh runtime files are untracked; current tests/docs/examples/wheel are also largely working-tree material. HEAD does not reproduce the reviewed product. The archive does. |
| F3 | Medium-High | **Root README describes an older command/product surface as if active.** | It documents commands such as `metaform service`, `metaform browse`, `metaform intake`, `metaform drive`, old module manifests, workflow/knowledge operations, and older namespace material. The active entrypoint is the fresh chassis; `docs/plugin-api.md:349-359` correctly says old feature commands live under `legacy_cli` and intake/workflow/layers/MCP remain unmigrated. |
| F4 | Medium-High | **Web inspection data is unauthenticated when bound beyond loopback.** | `examples/plugins/web/__init__.py:195-215` exposes `/projects`, `/records`, and `/provenance` without the bearer token; only `/_control/*` checks it. Since the module deliberately permits `0.0.0.0` or a specific interface bind, a non-loopback configuration exposes read access to project/record/provenance information to any reachable client. |
| F5 | Medium | **Fresh persistent store has no schema-version/migration mechanism yet.** | `plugin_store.py` initializes tables with `CREATE TABLE IF NOT EXISTS`; no fresh-store schema version or ordered migration path is present. That is workable for the current development slice but becomes fragile once the one global persistent store evolves. |
| F6 | Medium | **Global host startup inherits the initiating client's entire `sys.path`.** | `runtime_client.py:76-82` serializes `sys.path` into `PYTHONPATH` for the persistent host. Because the host is global and survives clients, project/CWD-specific import paths from the client that starts it can influence later plugin imports. This is an architectural risk inferred from the code; I did not observe a failing test caused by it. |
| F7 | Medium | **Plugin contract has no explicit API compatibility/version field.** | `Plugin` currently carries id, operations, commands, settings, subscriptions, lifecycle, visibility and help, but no contract version. A future incompatible contract change would be discovered through import/activation failure rather than an intentional compatibility decision. |
| F8 | Medium | **Distribution metadata still mixes fresh chassis and legacy feature dependencies/tooling.** | `pyproject.toml` declares MCP, Flask, build, hatchling, Rich, and Questionary as base dependencies even though the fresh chassis itself uses a smaller subset. `tools/build_distribution.py` still imports legacy `App`, `metaform.packaging`, and old service shutdown. The executable wheel works, but the packaging boundary is not yet as clean as the fresh architecture boundary. |
| F9 | Low-Medium | **Current local runtime has no explicit admission/backpressure policy.** | Jobs/events can create work freely, sync work uses worker dispatch, and SQLite writes serialize through immediate transactions. This is suitable for the current local chassis, but it is not yet a bounded high-load runtime. No current requirement says it must be a distributed/high-throughput broker. |
| F10 | Low / documented constraint | **CLI clients import plugin Python to reconstruct Click commands.** | This preserves complete module-owned Click commands and clients do not run lifecycle hooks, but Python top-level module code still executes on import. The project already documents plugins as trusted executable Python and teaches authors to acquire runtime resources in lifecycle hooks. |

## 7. Canonical Intake compatibility: exact issue

The current Canonical Intake states that the EF belongs semantically to the PE but is recorded in the RE-owned join for that specific encounter, because one PE can provide different EFs to different RE OPs. It explicitly says not to create element-level EF records outside joins.

The existing legacy conversion says the opposite structurally:

`src/metaform/coarse.py`:

> “notable elements keyed by namespace position with one EF each, and joins carrying the receiver's Operative Purpose.”

It then accepts only `{"ef", "name_length"}` on an Element and treats EF as mandatory. Its joins accept receiver/provider/purpose/relation/observation/combined/refs but not encounter function.

`src/metaform/answers.py` likewise requires an `<ef>` on each Element, writes it into the Element record, and does not carry a join EF into its contribution.

This should be treated as **old implementation semantics**, not adapted by merely changing field names. The intake migration needs to start from the current canonical relation:

```text
RE-owned join
    OP       -> belongs to the RE
    PE ref   -> identifies the Providing Element
    function -> EF belonging to that PE in this encounter
```

The namespace object itself retains the PE's reusable functional identity; the join retains the encounter-specific function and receiving purpose.

## 8. Strengths worth preserving

The following parts are notably sound in the reviewed implementation:

- The fresh chassis is genuinely independent of individual feature modules.
- Public service imports resolve active context rather than constructing hidden parallel state.
- Module removal withdraws executable contributions without deleting retained data/settings.
- Context isolation is taken seriously and tested across concurrent assignments.
- Sync/async behavior is explicit; cancellation does not pretend a thread-backed callable stopped when it did not.
- Assignment/header routing is durable and tested rather than relying on PID/transport identity.
- Finalization is ordered so durable completion precedes marker cleanup.
- Event failures remain attributable and isolated.
- Settings/glue behavior has strong behavioral coverage, including concurrency repairs.
- Plugin discovery handles source changes, disabled modules, removal, and broken plugins without destroying administration.
- The executable-wheel route is real, and its package bytes correspond to the captured source.
- The code and current `docs/plugin-api.md` are unusually honest about the migration boundary.

## 9. Current implementation boundary

### Implemented in the fresh chassis

Module lifecycle, public services, contextual CLI, settings/glue/TUI, project-scoped records and basic provenance, durable assignment/header mechanics, shared runtime, jobs, events, process tracking, plugin discovery/disabled policy, example modules, optional small web inspection module, and executable-wheel operation.

### Present in the repository but not migrated into the fresh chassis

Intake, workflow conversion/execution, layered graph evaluation, MCP adapters, and significant older project/history/portable functionality. These older implementations are useful evidence and may contain reusable mechanics, but they are not proof of integration with the new chassis and in at least the intake case they carry superseded semantics.

### Specified but not established complete

Full canonical namespace/join storage, current Canonical Intake execution through common workflow machinery, full object-oriented provenance mirror, knowledge layers/selection, memory, complete origin/variant reconstruction, portable project closure, full workbench, and the rest of the whole-product specification.

## 10. Recommended next actions

These are suggestions from the review, not changes made to the archive:

1. **Checkpoint the fresh chassis state in version control** before further migration so the reviewed implementation is no longer dependent on an archive/untracked workspace.
2. **Treat Canonical Intake migration as a semantic rewrite of the old adapter, not a field migration.** In particular, remove the one-EF-per-Element assumption and retain PE EF on each RE-owned join.
3. **Bring the root README to the same implementation boundary as `docs/plugin-api.md`.** Keep legacy commands explicitly labeled as legacy rather than appearing to be the active chassis CLI.
4. **Decide the exposure contract for the web inspection endpoints before recommending non-loopback bind.** If non-loopback inspection is intended to stay public, document that explicitly; otherwise apply the same instance/auth boundary to the read endpoints.
5. **Add explicit store schema versioning/migration before the fresh global database accumulates durable user state across revisions.**
6. **Make persistent-host import resolution independent of whichever project/client starts the host.** Preserve required package/plugin paths deliberately rather than copying the whole client `sys.path` into a global long-lived process.
7. Later, when the public plugin API begins supporting external third-party modules across releases, add an explicit compatibility/version contract.

## 11. Bottom line

The chassis foundation is in good engineering shape for its declared current scope. Its core runtime behavior is implemented, the focused verification is credible, the preserved wheel corresponds to the captured source, and the major mechanisms hold up under independent rerun/manual reproduction.

The project is **not yet in a clean integration state**. The main chassis implementation is mostly untracked, the active documentation surface is split between old and new behavior, and the legacy feature stack remains adjacent to the fresh runtime. The next migration work must be selective rather than mechanical.

For the current design discussion, the most important concrete conclusion is: **do not reuse the legacy `answers.py`/`coarse.py` intake representation as the semantic basis for the new Canonical Intake.** It encodes a single EF on the Element, while the current design correctly permits the same PE to provide different EFs in different RE-owned joins.
