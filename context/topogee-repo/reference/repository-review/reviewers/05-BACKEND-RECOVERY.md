# Reviewer 5: backend compatibility and September LadybugDB recovery

Independent first pass frozen on 2026-10-29. No other reviewer's findings were read before this report was written. Scope is persistence and the transitive storage dependencies of potential reuse, plus recovery of historical LadybugDB work. This report proposes no implementation changes.

## Source and method

- Target: remote `main`, `fceef55a2fb6bd9bf5f8a46310e1af84276fa9f9`, inspected in `/tmp/metaform-review-20261029-fceef55a`.
- History: `/home/rich/metaform`, initially clean `main` at `261a1cb7172159b4354308a423028a86ffc179f3`, ahead one/behind two relative to the target. No checkout/reset/stash/commit occurred.
- The owner's amendments A-F govern. LadybugDB selection is settled. Existing SQLite contracts describe legacy behavior, rather than target requirements or permission to retain SQLite runtime islands.
- Read applicable root instructions, `metaform-dev/SKILL.md`, `bmad-review/SKILL.md`, its customization and adversarial/edge-case references. Applied evidence-based challenge and path tracing without the adversarial finding quota, as the user's instruction requires. No project `_bmad` runtime is present, so installed customization defaults were read directly. No historical assignment or executable was activated.
- Parent graph evidence was only a navigation hint: local project `home-rich-metaform`, generation `2026-10-29T06:06:33Z`. The graph indexes the diverged checkout. Conclusions below use directly read source at the pinned target or explicit historical revisions.
- `reviewer05-evidence.json` retains all 559 inspected Git ref identities, nine root ZIP digests and keyword-hit members, and the current lexical SQL-coupling candidate list. Candidate lists are not assertions that every file is reached by every caller.

The principal conclusion is **adapt the useful persistence contracts and replace the storage realization**. A public `Store` or `TableTx` API is not a backend-independent implementation. The owner correctly remembers real September Ladybug integration. It had an actual native driver and callers, but its schema and shared-service authority model do not implement the selected ECS target.

## Target contract used for comparison

`ecs/Inference-Metaform-ECS-Terminology-Review.zip` SHA-256 `046eafd31b067e32dee11e5fec08fbfe60c17de7cfba848957721f806de3a9e4`, member `03-technical-specification.md`:

- Lines 17-29 distinguish semantic Address identity, RE-owned OP/EF and compatibility import from new canonical interaction.
- Lines 35-41 separate published `MapSnapshot` and mutable runtime revisions. A graph descriptor cannot pretend an external resource is frozen.
- Lines 65-137 and member `contracts/graph.cypher:1-69` define typed snapshot-qualified Namespace, Element, PurposeJoin, Layer, ContextItem and RuntimeRecord records, with typed relationships. Storage keys use length-prefixed `(snapshot, kind, logical identity)` inputs, separate from semantic Addresses.
- Lines 151-159 require materialized ancestry, incidence and source records to publish together. The reference realization has a single database service/write queue and multi-query read transactions.
- Lines 654-694 require participant/context/epoch/delivery/message/work/handoff/wake records and revision-aware mutations that preserve incompatible concurrent contributions.
- Lines 602-637 describe an event journal with a transactional head and sequence-keyed RuntimeRecords, replayable identities and unknown outcomes after ambiguous ACP submission.

`next_spec/metaform-specifications-2026-10-28.zip` SHA-256 `0ed29b853d95f01f4bd545c7fb68380962abce3831f4f31d439ae3a13963bcb9`, members `SPEC.md` CAP-1/6/10/12/13/15 and `acceptance.md` AC-01/06/10/12/13/15 corroborate these requirements. Owner amendment B closes the otherwise tempting SQLite exception for settings, conversations and receipts. Owner amendments C-F refine delivery, events, Python-Node ownership and sensor behavior. Nothing here changes their settled decisions.

## Transitive persistence map

| Entry / candidate | Reached persistence and exact evidence | Reuse consequence |
| --- | --- | --- |
| CLI, MCP or module command | `src/metaform/context.py:22-45` builds settings and `Store`; `src/metaform/module.py:603` embeds module table declarations; `module.py:725` returns the concrete store | Share domain services across surfaces, but preserve neither SQL reach-through nor automatic CLI-to-MCP inventory as a target contract |
| Module loader/settings | `src/metaform/settings.py:329-369` resolves inherited values through `home.stored`/`glued`; `settings.py:417-419` writes through `home.save` | Settings declarations/validation can survive a repository boundary. Their resolver is transitively persistent |
| Home and project registry | `src/metaform/home.py:46-123` declares settings, glue, aliases, installs, module state, projects, bases and active bases; `home.py:362-381,441-445` opens SQLite transactions | Replace storage for every retained category, including global/home data, rather than only the map |
| Domain Store | `src/metaform/data/store.py:71-97,110-130` reaches `home.project` then `Session` and SQLite error handling; `store.py:339-344` reaches refinement | Adapt domain intent methods and transaction scoping to target graph/snapshot services |
| Current graph | `src/metaform/data/session.py:139-157,214-243` opens SQLite, obtains a process projection, appends ops and commits; `data/schema.py:1-15`, `data/log.py:20-32` define authoritative op log and cached snapshots | This is a SQLite event-sourced model with a derived in-memory graph, not an interchangeable graph driver |
| Cypher | `src/metaform/data/reads.py:596-636` creates a NetworkX filtered view; `data/projection.py:396-399` invokes `grandcypher.GrandCypher`; `pyproject.toml:28` lists NetworkX and grand-cypher | Existing Cypher tests are not LadybugDB integration evidence |
| Module records | `src/metaform/data/store.py:399-440,447-467` selects map/project files; `data/tables.py:1079-1122` binds a SQLite connection; `tables.py:630-649` introspects SQLite PRAGMAs | Module-owned data must be re-expressed behind typed storage operations, not left in module `.sqlite3` files |
| Intake assessments | `src/metaform/modules/intake/__init__.py:222-230,234-235` declares current/history tables and obtains a bound Store | Assessment history can be preserved as data, without retaining intake choreography or table API |
| Context/role receipts | `src/metaform/modules/agents/roles.py:17-45` stores generated role sources, history, epochs, actual/selected versions, fingerprints and change notices via project tables | Valuable fields and delivery distinctions, but the receipt service must move with runtime state |
| Memory/knowledge | `src/metaform/modules/memory/__init__.py:127-162` declares project entities, observations, relationships, RE links, notes, citation digests, mutation receipts; `memory/delivery.py:29-47` declares encounter/delta/withdrawal state | Adapt knowledge and delta mechanics together. Keeping receipt SQLite while moving memory bodies would split the semantic operation |
| Dispatch sessions/conversations | `src/metaform/modules/dispatch/__init__.py:152-180,185-188,236-245` declares current project sessions/transcripts/signals/spend/attempts and legacy map-level copies | Preserve conversation independence from map clearing, not the current project-file split |
| Orchestration | `src/metaform/modules/orchestration/state.py:212-258` declares assignments, sessions, durable transitions/delivery, role requests and version changes | Storage adaptation is mandatory even for retained orchestration logic. Legacy mandatory roles/approval semantics require separate redesign |
| Prompt payloads | `src/metaform/prompt_files.py:334-355,401-414` selects file, trial, stored edit or last valid shipped text; `data/prompts.py:249-267` reaches `prompts.sqlite3`; `data/prompts.py:47-78` keeps immutable versions/use links/aliases | Preserve exact selected-version provenance and fallback mechanics while replacing the prompt repository |
| History, origins, variants | `src/metaform/data/history.py:34-66,201-215` stores manifests/lineage in `history.sqlite3`, payloads in files; `home.py:1478-1492` copies SQLite via its backup API | File payload mechanics are useful. Metadata and backup orchestration require target-aware adaptation |
| Item counters | `src/metaform/data/numbers.py:57-84`, `Session.Tx.number` at `data/session.py:129-133` allocates in `project.sqlite3`, independently of the map write | Do not silently retain a separate SQLite counter. Preserve the required non-reuse property only where the target reference contract adopts these short numbers |
| Change notifications | `src/metaform/changes.py:42-80` uses SQLite authorizers and `total_changes`; `data/session.py:238-243` notes changes after commit | Adapt after-commit publication and concern metadata. Replace SQLite-specific write observation |
| Caches | `src/metaform/home.py:250-269` watches `.sqlite3`/WAL filesystem stamps; `data/log.py:36-90` catches a cached projection up by SQL sequence | Replace invalidation keys with explicit target snapshot/runtime revisions. Preserve coalescing/filtering concepts |

This covers the storage entry points reached by the requested reuse candidates. It does not claim exhaustive dynamic reachability of every optional module. The lexical appendix identifies additional candidates for later bounded extraction review.

## Evidence-based candidate assessments

### B-01: Store/session/projection is a different data model

**Type:** correct legacy behavior conflicting with rebuild. **Classification:** re-engineer or replace storage realization, adapt domain services.

**Trigger:** retain `Store` unchanged and swap its connector for LadybugDB. **Observed:** `data/session.py:214-243` requires a SQLite transaction plus a shared `Projection`; writes update that projection before appending the log. `data/log.py:77-90` reconstructs current state from JSON snapshots and ordered SQL ops. `data/schema.py:1-15` explicitly says no current element/join table is authoritative. `data/projection.py:47-56` emulates old row shapes, even presenting its sequence as `row`.

**Requirement/consequence:** ECS snapshot-qualified graph records and derived topology cannot be satisfied by replacing import/driver names. Old UUID identities, sequence rows, synthetic edges and cached projections must not become hidden target contracts. A Ladybug log backing the same old projection would still leave the model redesign undone.

**Smallest boundary:** preserve semantic inputs/results and atomic-publication invariants, introduce target graph read/write services that own snapshot and runtime revisions, and adapt callers instead of emulating SQL rows indefinitely. `Store.atomic()` is useful scoped ownership, but all source/derived writes must join the new publication transaction.

**Callers/tests inspected:** context construction above, module extension operations at `store.py:88-96`, `tests/test_store_log.py:43-85,110-133,147-170` checks append-only ops/replay and NetworkX Cypher. `tests/test_store_concurrency.py:38-80` checks SQLite file integrity and transcript row count. These are valuable legacy protections, not target backend proof.

### B-02: public module storage and approved template carry SQLite assumptions

**Type:** useful mechanics with incompatible transitive dependencies. **Classification:** adapt the permitted chassis/template, replace its relational storage portion.

**Trigger:** start a new module from either template and use documented persistence. **Observed:** `src/metaform/modules/template/__init__.py:26-47` advertises `Tables`, `Table`, `Column`, `Index`, `Store.tables()`, joined transactions and `Table.from_sql`; the fork copy advertises the same contract at `src/metaform/modules/fork/resources/template/__init__.py:13-41`. `data/tables.py:1079` defines the opener as returning `sqlite3.Connection`; `tables.py:630-649` depends on SQLite PRAGMA/schema inspection. `data/session.py:65-67` publicly gives composite handlers raw SQL execution.

**Requirement/consequence:** permission to reuse the template does not establish backend independence. Blind copying would retain SQLite by the sanctioned public base itself. Keep lifecycle, owned capabilities, request identity and version declaration concepts, but change persistence examples/declarations to supported target services and retire SQL reach-through for new modules.

**Smallest boundary:** separate module metadata/lifecycle from storage service contracts. Preserve typed module records only where they fit target graph or RuntimeRecord shapes. Explicitly document which operations join one graph publication and which act on external/native providers.

**Callers/tests inspected:** Store.tables path above, `Module.tables` at `module.py:603`; `tests/test_module_tables.py:23-61,99-126,129-155` proves typed rows, two storage lifetimes and indexed paging. Its SQL table names and PRAGMA assertions constrain the legacy implementation, rather than the target.

### B-03: settings and registry are runtime state, not a SQLite exception

**Type:** correct legacy behavior conflicting with owner amendment B. **Classification:** adapt declarations/resolution, replace persistence and cache invalidation.

**Trigger:** an operator changes a setting, or a CLI/MCP call resolves inherited configuration. **Observed:** `settings.py:339-369,417-419` reaches home storage. `home.py:746-768` serializes member values as ordered JSON SQL rows. `home.py:250-269` invalidates on database/WAL file identities; `home.py:771-779` announces affected projects after commit.

**Requirement/consequence:** retaining settings/home SQLite would violate the explicit no-assumed-exception rule and keep SQLite transitively reachable from every command. The target packet does not yet spell out every settings payload; that is a specific contract-completion task, not reopened database selection.

**Smallest boundary:** a settings repository preserving scope, owner, order, explicit unset/empty/default and inherited-source metadata. Store global and project runtime state through an explicit selected-backend arrangement, with revision-based invalidation and after-commit notifications.

**Callers/tests inspected:** `context.py:22-45`, `instructions.py:26-33`; `tests/test_settings_changes.py:12-30` checks scope-related project notifications, `:33-46` checks per-call coalescing and `:60-85` distinguishes schema installation from meaningful changes. Preserve these observable concerns, not SQLite authorizers.

### B-04: prompt source bytes and actual selected versions are worth preserving

**Type:** useful mechanics surviving a persistence boundary. **Classification:** adapt.

**Trigger:** shipped text changes after a saved edit, a malformed prompt appears, or an old layer references a prior prompt. **Observed:** `data/prompts.py:3-9,55-73` keeps immutable version parents, edited/shipped origins and uses; `prompt_files.py:334-355` selects edits and renders fills; `:401-414` can fall back to prior valid shipped text. `data/prompts.py:249-267` uses a separately versioned SQLite store and `:127-144` implements writable compatibility views for older SQL consumers.

**Requirement/consequence:** preserve source/version identity through actual rendering. Reusing just XML parser mechanics while discarding version selection would lose an implemented benefit. Keeping `prompts.sqlite3` or old SQL alias views would preserve the wrong dependency.

**Smallest boundary:** retain parse/render/fallback behavior and the selected/actual version fields through a prompt-source repository whose target persistence owns immutable prompt bodies, edit lineage and use references. Separate persistent provenance from current runtime selection. Do not infer the prompt a model saw from the file alone.

**Callers/tests inspected:** `instructions.py:54-59`, `views.py:15` and `prompt_files` calls; `tests/test_prompts.py:21-37,42-66` verifies immutable ancestors, pinned layer use and edited-text precedence. `:71-89` tests SQLite query plans specifically. None of these tests establishes target graph compatibility or model comprehension.

### B-05: delivery, conversations, knowledge and orchestration state must move together by contract

**Type:** useful mechanics and correct legacy separation conflicting with target realization. **Classification:** adapt runtime service boundaries, replace storage mechanics.

**Trigger:** clear/switch a map, reopen a dormant worker, compact, correct memory, or recover a transition delivery. **Observed:** current project-level tables deliberately preserve conversations and receipts outside map files. `dispatch/__init__.py:141-148,173-188` documents and declares current and historical locations. `agents/roles.py:28-45` stores epoch and actual/selected payload identity. `memory/delivery.py:29-47` stores encounters, pending changes and withdrawals. `orchestration/state.py:235-240` persists transition payload/delivery state.

**Requirement/consequence:** preserve independent logical identity/history and once-per-epoch changed-body delivery, with observable receipt meaning. Moving map objects alone leaves backend-dependent runtime behavior intact. Do not label these legacy tables a complete target event journal: their transition work is not the ECS general head/sequence/event-origin contract.

**Smallest boundary:** enumerate RuntimeRecord/native-provider contracts for contexts, receipts, prompt/skill loading, messages, sessions, transitions and spend. Preserve each source version and epoch through the actual transport boundary. Add a general event journal keyed by stable source/event identity with transactional cursor/head changes. This review does not mandate approval roles or implement retention claims.

**Callers/tests inspected:** `Store.tables` path and state declarations above; `memory/tests/test_delivery.py:282-307` verifies a concurrent correction remains unread until emitted, `:342-347` makes current memory due after explicit epoch advancement, `:447-458` shares receipts across isolated CLI calls. These prove useful deterministic mechanics on SQLite, not harness retention or actual draft-event support.

### B-06: serialized writes do not provide stale-contribution reconciliation

**Type:** correct legacy behavior conflicting with the target concurrent contribution contract. **Classification:** adapt semantic mutation boundary.

**Trigger:** two contributors read one version then submit incompatible changes. **Observed:** `Store.refine` at `data/store.py:339-344` accepts identity/changes/reason/evidence/by, without observed revision or operation ID. `data/layering.py:323-373` reads whichever version is current in its transaction and emits a later version. `Session.write` serializes database commits, but cannot reconstruct the contributor's observed source from that signature.

**Requirement/consequence:** ECS `03-technical-specification.md:692-694` requires preserving incompatible proposed values and returning `concurrent_change`, not merely keeping older overwritten versions somewhere in the log. Legacy physical integrity tests do not demonstrate that user-visible reconciliation.

**Smallest boundary:** coherent semantic submissions carry operation identity and observed snapshot/record revision. The graph publication transaction returns accepted revision or explicit conflicting contributions. Preserve history and supplied reasoning from both parties, without an inferred reviewer pipeline.

**Tests inspected:** `tests/test_store_log.py:43-59` proves append-only history; `tests/test_store_concurrency.py:38-80` proves six concurrent writers preserve a SQLite file and line count. Those assertions are narrower than stale semantic contribution preservation. Symbol searches for observed/concurrent/expected in `data/layering.py`, `writes.py` plus the inspected refine signature define this finding's bounded scope. No claim is made that every optional module lacks its own concurrency checks.

### B-07: preservation and recovery mechanics are assets, with a target-aware boundary

**Type:** useful mechanics. **Classification:** adapt metadata/coordination, reuse suitable file/digest routines after extraction.

**Trigger:** backup/restore, source-bound document composition, or failed history publication. **Observed:** `data/history.py:34-66,201-215` combines SQL lineage with retained file payloads; `home.py:1478-1492` backs up live SQLite via the database API and skips WAL sidecars; `data/upgrade.py:1-11` describes copy-before-upgrade. Historical Ladybug staged-copy publication described below retains old complete output on failure.

**Requirement/consequence:** retain immutable input/source capture, digests, parent provenance and staged publication. SQLite backup cannot back up LadybugDB, and a file copy without its engine's consistent-state contract is insufficient. Do not carry the old SQL schema upgrade chain into the target as an assumed migration algorithm.

**Smallest boundary:** target snapshot/export and runtime-cut services produce immutable manifests. Filesystem staging/hash verification can remain behind them, with explicit recovery records for cross-resource publication. A later migration design must name target identities and preservation proofs before touching data.

**Tests inspected:** `tests/test_history.py:97-119` checks commit/digest and source retention; `:307-320` injects failed publication and checks no variant rows/folders remain. These are positive preservation evidence, not Ladybug backup evidence.

### B-08: exact pure Address presentation is a narrow reuse foundation

**Type:** useful compatible semantics. **Classification:** reuse substantially unchanged at the routine-body level, adapt package/import boundary.

**Trigger:** present a semantic Address's reading or short name. **Observed:** `src/metaform/data/names.py:16-28` reverses segments, expands underscores and selects `name_length` without storage calls. `data/ids.py:44-47` derives trunk-first prefixes. Their algorithms have no SQL or engine dependency. The enclosing `metaform.data` package and callers currently lead back to Store, so this is not approval to reuse the entire package unchanged.

**Requirement/consequence:** preserve canonical Address meaning and namespace traversal while keeping namespace ancestry distinct from RE/PE relationships. Reuse these small bodies behind an independent semantic utility boundary if the target keeps the same formatting contract.

**Callers/tests inspected:** `data/views.py:17,45-51` consumes reading/short_name; `data/projection.py:26` imports prefixes. `tests/test_store_map.py:145-164` observes `kitchen timer` / `kitchen timer code` and element identity fields. It is a semantic utility assertion embedded in a storage fixture, not a target backend test.

No storage defect against the inspected legacy contract is asserted merely because that behavior differs from the rebuild. B-01/B-03/B-06 are target incompatibilities. B-02/B-04/B-05/B-07/B-08 identify useful mechanics and the minimum boundary preventing their transitive dependencies from being mistaken for portable implementation.

## September LadybugDB recovery

### Pinned chronology and artifact identity

| Artifact/revision | Observed capability and exact evidence | Target fit and recovery recommendation |
| --- | --- | --- |
| `98926298ae96be0be5f1e7282ff5cfb2492fa506`, 2026-09-06 | `src/metaform/backends.py:176-202` already defines `LadybugGraph.connection`, imports `ladybug`, opens native Database/Connection and Record/Participant tables | Real native adapter source. Recover mechanics as reference, not the later target ontology |
| `8c2f4a3ae6f8d858a14939f11a85450d9d5f3157`, 2026-09-10 | `backends.py:213-462`, `service.py:155-239`, `modules/graph.py:57-113`, tests below provide native read/write, shared-service analysis copies and revision-labelled Cypher | Best recovered reference cut. The old multi-backend authority model is incompatible with amendment B |
| Same commit, manifest | `pyproject.toml:11` declares `ladybug>=0.20.2,<0.21`; `uv.lock:393-404` records PyPI `ladybug==0.20.2` with native wheels and sdist digest `ebf6a2c3469a34cff3b1e3b83e9e782e624a8ae73aad433b9ec2e74a503879de` | Establishes actual package, rather than inference from a name/Cypher string. Current driver/version/API validation remains future integration work |
| Retained `/home/rich/metaform/metaform.zip`, SHA-256 `7705d9bd2bd634e503be73e13cb34f225cfffe88b5477e99a096b48d527110b6` | Members `src/metaform/backends.py` and `src/metaform/service.py` are byte-identical Git blobs to Sept10: `8aa32da2989df75719a19a7e2eaeb4b0264b5804` and `bf6eec0ffc59d5e826d763ff74a6c95325ebf025` | Independent retained recovery source, no execution needed. Member SHA-256: backends `4b50d6d57c0cbf451828ea0dd76e5268b9c96cc25eb16313a6d825e6bfd44b67`, service `fae5cfbba7b6f6c7a7e0ac7d119a389f16935fceac308628f78ea9749adda51e` |
| `3d3543bc84047d86faac59e3533f3f92fcbd72aa`, 2026-09-11 | `backends.py:211-220` now recognizes SQLite/JSON only; `tests/test_knowledge_store.py:260-285` explicitly refuses retired `ladybug` while preserving files | The checkpoint is evidence of removal, not the pre-removal implementation. Do not use it to conclude Ladybug never existed |
| Retained `metaform_2.zip`, SHA-256 `7be9449087fac8b681000a461ae02a7a9854d4d127dc772f13f2261f3be5d196` | `src/metaform/backends.py` has the 220-line post-retirement implementation. `docs/reviews/final-distribution/dependencies311.json:28` and `dependencies313.json:28` mention Ladybug 0.20.4 | Archive dependency mentions can outlive code removal. Do not treat old dependency reports as proof that this archive actively uses Ladybug |
| `6d991b7a8bf15bfdb2500adc2aef96eb1109a2e6`, 2026-09-21 | `git log -- src/metaform/backends.py` records removal of earlier runtime and old adapter file | Explains why current main has no driver adapter. Recovery should be selective, rather than resetting to the earlier runtime |

### What the recovered integration actually did

1. **Native engine ownership:** Sept10 `backends.py:220-239` takes a cross-process `FileLock`, opens `ladybug.Database(path, buffer_pool_size=128*1024*1024)`, opens a `Connection`, ensures typed tables, and closes both in `finally`. This is actual native engine API use, not NetworkX grand-cypher.
2. **Schema:** `backends.py:230-235` has one generic `Record` node table with `id/kind/name/description/layer/scope/object_id/element_id/body`, and `Participant` relationships with `role/ordinal`. `backends.py:361-393` stores generic JSON bodies and join incidence. This does not match Namespace/Element/PurposeJoin/ContextItem/RuntimeRecord or target snapshot-qualified keys.
3. **Queries/results:** `backends.py:241-259` executes parameterized Cypher and returns column names plus row arrays, converting unsupported JSON values to ISO strings/strings. `:396-446` exports and queries whole Record bodies. New typed result contracts must preserve native schema/bytes rather than inheriting this catch-all coercion.
4. **Write transactions:** `backends.py:261-299`, `:301-359` explicitly BEGIN/COMMIT/ROLLBACK bulk put/rename/replace. `replace_scope` reads the old graph, deletes all Record nodes and rehydrates. This proves transaction mechanics exist in source, not a performance-safe target update algorithm.
5. **Legacy direct graph mode:** `app.py:171-196` selects `open_graph(..., 'ladybug')` for project/global graph files when not service mode; `modules/graph.py:84-98` can copy a prior graph to the chosen backend and set configuration. This was a usable native graph persistence path, not solely an unused adapter.
6. **Shared-service mode:** `app.py:173-175,187-189` routes graph access to `BoundGraph`; `knowledge.py:310-366` keeps authoritative elements/joins/participants/receipts/revision in SQLite. `service.py:193-239` builds explicit disposable Ladybug analysis copies from a consistent SQLite export, records `source_revision`, and publishes complete copy plus metadata under a lock. Query writes affect the analysis copy only.
7. **Installed wiring:** `installation.py:34-37` detects `ladybug` and invokes graph backend selection. `modules/graph.py:60-80` refreshes project/global analysis copies in service mode, and `:101-113` routes Cypher through the service or direct graph.
8. **Failure/identity:** `service.py:155-178` carries request/project/protocol/service/instance identity. For `analysis.query`, a dropped response yields `ambiguous_result` instead of automatic replay at `:164-166`. The native query might mutate its copy, so pretending retry is harmless would be incorrect. Retain this uncertainty distinction in future semantic channel design.

### Tests and historical execution evidence

Read at Sept10, not executed in this review:

- `tests/test_service_analysis.py:18-40`: refresh/query owner-scoped native/archaeology observations, stable source revision until refresh, updates after refresh, writes isolated to the copy and refresh restoring authoritative data.
- `:43-53`: missing copy, invalid owner and unsupported backend handling.
- `:56-68`: concurrent queries see complete 20- or 60-element copies, never intermediate hydration.
- `:71-94`: graph commands route to service analysis, while portable JSON does not silently create native storage.
- `:97-125`: deliberately unavailable native engine leaves SQLite core/export working, confirming native analysis was separate from authority in that mode.
- `:128-157`: a query response is deliberately dropped, an ambiguous result is returned and the mutation is observed once in the copy, without changing authoritative graph data.
- `:165-180`: other-project global refresh changes source metadata seen through backend status.
- `tests/test_knowledge_store.py:99-114`: source-preserving adoption of actual SQLite/JSON/Ladybug legacy graphs into the service.
- `tools/check_distribution.py:227-231`: installed-distribution check refreshes native analysis and asserts Cypher result plus matching source revision.

Historical records are corroboration, not new results: Sept10 `docs/verification.md:100-109,121-139` reports installed Ladybug/Cypher checks while explicitly excluding live model trials and large-corpus performance proof. `docs/reviews/2026-09-09-system-review-evidence/baseline.json:10-25` records Ladybug 0.20.2/0.20.3 and prior suite/distribution success. Sept11's `docs/reviews/2026-09-11-ladybug-retirement-owned-tests.log:1-3` records 101 passes on retirement-era owned tests, not target integration. The ECS packet's `verification/results.json` explicitly lists LadybugDB DDL/Cypher as unexecuted. None was rerun here.

### Recovery recommendation

Recover the Sept10 adapter and service mechanics as separately reviewable reference material: parameter binding/result iteration, explicit transaction rollback, cross-process engine ownership, complete-copy publication/source revision, request identity and ambiguous-outcome reporting. Re-engineer graph schema, typed projections, revision keys, runtime persistence, long-lived service ownership and write scheduling for the ECS model. Do not restore the old command inventory, installer-driven backend migration, arbitrary Cypher agent choreography, generic Record/JSON ontology, SQLite authority or portable-mode exception as target behavior.

The immediate additional evidence needed is a focused future spike against the selected current LadybugDB driver and target DDL, exact result types/NULL handling, multi-query read snapshots, rollback, single-writer queue, derived ancestry/incidence publication and preserved historical views. It must include runtime records and recovery, rather than a `RETURN 1` engine smoke test alone. This is proposed work, not authorization or a claim of implementation readiness.

## Search scope, commands and limits

Executed read-only command families:

- `git log --all -i --grep='ladybug\|lbug\|kuzu' --format=...`, `git log --all -- .../backends.py`, `git log --all -S 'class LadybugGraph' -- src/metaform/backends.py`, and September date-bounded history.
- `git rev-list --all --count` returned 1591, `git rev-parse --is-shallow-repository` returned false. `git for-each-ref --format=...` captured 559 local branches, remote tracking refs and tags in the appendix. `git rev-list --all --objects` searched historical Ladybug/Kuzu/lbug paths.
- `git ls-tree -r --name-only <revision>` and `git grep` at candidate revisions, then `git show <full commit>:<path>` with `nl`/`sed`/`rg` to inspect pinned source/tests/manifests. Sept10 source blobs were compared using `git hash-object --stdin` and ZIP member hashes.
- `rg -n -i 'ladybug|lbug|kuzu|cypher' pyproject.toml uv.lock src archive` at the target, then dependency/caller searches by `Store`, `tables`, `sqlite.opened`, SQL execution, receipts and session records. Some initial guessed paths were absent, including `data/tx.py`, module `schema.py` files and a historical `test_backends.py`; subsequent searches located actual owners. No absence conclusion relies on those guessed paths.
- Read-only Python ZIP listing/text scanning and SHA-256 over all nine root ZIPs. Text scan covered `.py/.toml/.txt/.md/.json/.yml/.yaml/.lock` members smaller than 5 MB. Selected `metaform.zip` source text was extracted only beneath the temporary review snapshot for line-addressable inspection. No archived Python, shell, generator, installer or migration script was executed.
- `rg --files` inventoried retained archive locations, including `rich/backups`. Those backups and nested archive payloads were not opened or modified. The successful recovery above makes them unnecessary to establish the historical native path. Remote branches not represented by available refs and unreachable/pruned Git objects were not exhaustively recovered.

Tests inspected are separated above from historical execution records. **Tests executed by this reviewer: none.** Existing deterministic source/tests resolved the material reuse questions without running storage writers or old service startup. `conftest.py:25-43,46-52` was read for isolated homes/fake-agent defaults. No database was opened, migrated or rewritten by this review. No paid session, production workflow, deployment, publish or commit was run. Future acceptance checks are proposals only.

## Specific remaining decisions and extraction order

1. Complete the target service/repository boundaries and typed payloads for global/project settings, prompt versions, sessions/conversations, counters, delivery/skill records, event journals and history. LadybugDB selection remains settled. External/native-provider ownership must be explicit rather than an inferred SQLite exception.
2. Resolve operation identity, observed revisions, conflict/result envelopes and immutable snapshot publication before adapting semantic intake or module operations. Preserve old IDs as provenance where imports need them without substituting them for target keys.
3. Extract pure Address presentation, parse/render, immutable file/digest and staged-publication mechanics only after identifying their package imports and callers. Preserve their useful algorithms, not unrelated legacy ontology or command wording.
4. Adapt permitted chassis/template metadata/lifecycle first against the new storage boundary, then re-engineer semantic MCP/intake and context delivery against those services. Do not postpone runtime state replacement until after the agent-facing interfaces are treated as complete.
5. Compare ACP placement using actual runtime ownership and the required asynchronous Python-Node channel. This backend review does not select Python or Node ownership and does not confuse the hosted module named `node` with Node.js.

This is an evidence-backed review and extraction recommendation. It establishes neither a completed rebuild nor an implementation-ready specification.
