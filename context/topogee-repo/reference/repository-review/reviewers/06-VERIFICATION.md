# Reviewer 6: independent verification inventory

Independent first pass, frozen before reading reviewers 1–5. Reviewed source is remote `main` at `fceef55a2fb6bd9bf5f8a46310e1af84276fa9f9`, extracted to `/tmp/metaform-review-20261029-fceef55a`. Paths and line numbers below refer to that revision. This report supplies evidence for reuse decisions. It does not certify the rebuild.

## Method and authority

- Applied the installed `bmad-review` workflow and verification-gap reference after reading their `SKILL.md`, customization and reference instructions. Its original changed-code framing was adapted explicitly to the owner-requested comparison between implemented contracts and rebuild acceptance contracts. No code change or legacy defect is inferred merely from a missing rebuild demonstration.
- Read `metaform-dev/SKILL.md`, root `AGENTS.md`, `CLAUDE.md`, `README.md`, `next_spec/README.md`, archived `SPEC.md` and `acceptance.md`, ECS verification README/results and relevant contracts. The only root/nested instruction matches in the pinned snapshot were `AGENTS.md` and `CLAUDE.md`.
- The repository has no `_bmad` directory. The coordinator resolved installed defaults through `/home/rich/_bmad/scripts`; missing repository configuration was recorded rather than repaired. No product discovery was restarted.
- Owner amendments A–F govern archival contradictions. In particular, neither archived axial-depth equivalence nor a compulsory local reflex supersedes amendment F's separate physical and virtual data/control profiles.
- Parent graph discovery was provisional: `home-rich-metaform`, generation `2026-10-29T06:06:33Z`, indexes the local checkout rather than pinned remote `main`. This report uses direct reads of the pinned source and makes no graph-completeness claim.

## Inventory and actual execution boundary

An AST-only inventory found **177 test files and 2,584 `test_` function definitions** under `tests/` and module-local `tests/`. This is a static count, not collected parametrized case count or an execution result. Group counts: chassis 693, dispatch 548, web 398, MCP 158, orchestration 136, map 116, memory 88, intake 74, roundtables 61, workflow 60, node 48, agents 37, autoticket 31, hello 26, twilio 24, cloud 19, packet 15, paperclip 15, fork 14, elevenlabs 10, voice 9, template 4.

- `pyproject.toml:48–60` discovers both trees, starts xdist workers by default, excludes `browser` by default and sets a 300-second timeout. `kind` is a descriptive marker, not proof of external integration.
- `pyproject.toml:63–70` configures strict source type checks while excluding tests. `.github/workflows/checks.yml:25–29` defines three OSes and Python 3.11/3.14, not evidence that those jobs passed for this commit.
- `.github/workflows/checks.yml:47–79` installs dependencies, builds a web map artifact using Node 22 and runs type/lint/default/browser checks. Its Node build step is not evidence of a persistent Python–Node runtime channel.
- `conftest.py:11–18` selects a temporary process-wide Metaform home before collection. `conftest.py:29–43,47–81` adds per-test homes, disables autostart and substitutes fake ACP agents unless a test opts into `product_defaults`; it clears the intake classifier credential.
- `conftest.py:113–164` normally invokes the real CLI entry point in-process. A `cli_process` marker, explicit option, running event loop or environment setting selects a separate process. In-process CLI success does not prove interprocess transport behavior.
- `conftest.py:61–63,150–152` seeds SQLite settings. Therefore even isolation/test setup needs adaptation when the retained state model changes.

**Tests executed for this independent pass: none.** Reads resolved the identified review questions. Running legacy SQLite/fake-harness tests would not create target-backend or real harness evidence, so no test run was used to imply it. No dependencies were installed, browser launched, paid model invoked or archive script executed.

## V1: retain the module-contract verification seam, adapt its persistence proof

**Classification:** useful mechanics, **Adapt** for chassis/template integration. Declaration-only portions are candidates for substantial reuse after dependency review.

- **Trigger:** an independent module is copied, enabled, loaded from a wheel or disabled while its retained data remains readable.
- **Observed evidence:** `src/metaform/modules/template/tests/test_template.py:28–47` checks declaration shape and actual enable/load of a copy; `:52–76` checks empty hooks and packaged toolbar/pane resources. `tests/test_base.py:43–54,93–98` starts separate Python processes to prove chassis import without module packages and no filesystem creation on public imports. `:126–153` executes a declared verb through CLI parsing and checks output/error behavior.
- **Positive protection:** `tests/test_module_data_source.py:33–90` loads retained declarations from folder/wheel resources without importing or starting the disabled runtime, and checks reset/extraction cleanup. `:111–132` verifies a broken unrelated declaration does not prevent reading a retained ticket.
- **Limit:** `tests/test_base.py:57–88` enforces allowed public imports and bans direct `sqlite3` imports. The public set explicitly includes `metaform.data`, `home` and `settings` at `:18–20`; this proves access discipline, not backend independence. `tests/test_feature_storage_boundary.py:10–18` itself executes SQLite DDL to verify table ownership.
- **Rebuild requirement:** amendment A permits chassis/template reuse; amendment B requires direct and transitive storage compatibility.
- **Smallest boundary:** retain declaration/loading/lifecycle expectations, replace storage-facing setup/contracts and demonstrate the copied module against the chosen target persistence services. Do not infer that the template works unchanged from shape tests.
- **Callers/storage inspected:** loader/data-source fixture calls above, module declaration imports and SQLite `STORE_SCHEMA`; `src/metaform/data/session.py:13,22,36–49,65–67` exposes a `sqlite3.Connection` and SQL execution inside its transaction type.

## V2: preserve deterministic payload/receipt assertions, adapt the storage and interface

**Classification:** useful mechanics, **Adapt**. No comprehension claim is supported.

- **Trigger:** a resource is reread in the same epoch, its selected prompt changes, an invalid edit falls back, compaction occurs, or shaping hides a body.
- **Observed evidence:** `src/metaform/modules/mcp/tests/test_mcp.py:4003–4045` reads rendered resource text, inspects stored receipt components, distinguishes selected/actual versions and fallback source kind, verifies unchanged omission and redelivery in a new epoch.
- **Positive protection:** `src/metaform/modules/memory/tests/test_delivery.py:179–229` proves counts/shaped-away bodies do not acknowledge delivery, and checks the transport identity rather than an unrelated process identity. `:282–307` changes content during response construction and verifies that the later revision remains unread. `:310–347` checks deletion/restoration notices and compaction.
- **Limit:** these paths use server functions and module tables. The receipt test calls `read_resource_text` directly at `test_mcp.py:4013–4018`; it does not inspect hidden native harness context. Memory tests demonstrate response/ledger effects, not model comprehension or retained skills after harness compaction.
- **Rebuild requirement:** amendment C separates discovery, delivery, skill loading, retention, source identity and epoch deltas.
- **Smallest boundary:** retain deterministic source/version and emitted-body tests as acceptance patterns, move receipts/epochs to the target runtime-record persistence boundary and add target response plus harness-observation assertions. An explicit unknown retention state remains valid.
- **Storage/callers:** `Store('proj', module='agents').tables` at `test_mcp.py:4011–4018`; prompt edit persistence at `:4028,4035`; `Store(..., module='memory').tables` at `test_delivery.py:223–224,337–339`.

## V3: retain no-flooding evidence, replace the blanket policy it currently protects

**Classification:** correct legacy behavior conflicting with the rebuild, **Re-engineer or replace** policy. Preserve scheduling/deduplication mechanics behind the new policy boundary.

- **Trigger:** a plain purposeful peer message reaches a recipient, versus a routine status update or an explicitly owned continuation.
- **Observed implementation:** `src/metaform/modules/dispatch/orchestration.py:477–505` admits selected message kinds and returns false for unlisted kinds, including ordinary `peer`; `:506–550` additionally checks assignment ownership/state. `Transport.send` at `:360–366` returns record-only before recipient lookup when disallowed. `runner.py:4481–4501` persists a disallowed note but starts a model turn only for allowed notes.
- **Tests actually read:** `test_informational_delivery.py:80–99` parametrizes plain `peer` with status-like kinds, expects zero prompt/resume/bytes and no piggyback, then confirms explicit history readback. `:129–181` proves owning continuations/questions can proceed and stale ownership is rejected. `:193–203,222–232` verifies UI notifications avoid transport lookup/model calls. `:237–311` uses a fake prompt transport to check duplicate delivery and restart receipts.
- **Rebuild requirement:** amendment D prohibits continual ticket/progress logging but permits purposeful peer communication and requires the explicit dynamic blacklist model. A general event adapter must preserve origin/meaning across supported MCP and chassis-local transports.
- **Consequence:** the zero-cost assertions are valuable, but carrying the present selected-kind gate unchanged would introduce the forbidden inferred allowlist. This is not evidence of a legacy bug against the legacy contract.
- **Smallest boundary:** decouple background status-recording rules from semantic message/event delivery. Keep zero model-turn/zero byte tests for routine updates; replace expectations that every ordinary peer message is passive with explicit dynamic blacklist and purposeful-message cases.
- **Dependencies:** session and delivery rows use `Store.tables` at `test_informational_delivery.py:35–40,94–96,245–248`; assignment-state fixtures are fake service objects at `:67–77`. They are not target journal or native MCP-event integration proof.

## V4: retain transport/cancellation failure scenarios as test designs, adapt the realization

**Classification:** useful mechanics, **Adapt**. **Requires additional evidence** for draft-event interoperability and the Python–Node channel.

- **Trigger:** another process changes the map, a live MCP connection encounters a schema upgrade, or a call is cancelled during server replacement.
- **Positive evidence:** `tests/test_relay.py:64–84` marks the CLI process boundary, writes in a separate process and waits for a listener event. `:118–128` checks self-echo suppression; `:135–147` launches an independent listener process and verifies the exact payload. These are stronger boundary observations than mocks.
- `src/metaform/modules/mcp/tests/test_mcp.py:43–58` uses an SDK MCP client and an actual stdio server subprocess. `test_module_discovery.py:96–109` exercises module resource discovery on that wire. This establishes a meaningful legacy server/client test seam.
- `test_upgrade.py:61–86` drives a live connection and directly counts a durable write after handover. `:133–175` checks a committed active call is not repeated. `:195–235` cancels active/buffered calls and checks settling and absent cancelled writes.
- **Limits:** upgrade fixtures copy the existing package and alter SQLite schema metadata (`test_upgrade.py:21–50`), with SQLite operation-log assertions at `:55–56,167–170,231–233`. They cannot establish LadybugDB transaction safety. `:178–191` opens a `subscriptions/listen` stream but does not assert general event payload, origin, capability fallback or Codex receipt.
- **Rebuild requirement:** amendments B, D and E require the new model/backend, capability/version-selected general events and an asynchronous Python–Node channel.
- **Smallest boundary:** preserve test scenarios and external-wire seam; implement target-specific state/failure assertions and transport adapters later. Add a genuine Python↔Node process test for session ownership, streamed correlation, cancellation and reconnect semantics after the contract is decided. Keep ACP placement open.

## V5: retain compaction and unavailable-session truthfulness

**Classification:** useful mechanics, **Adapt**, rather than proof of cache/retention behavior.

- **Trigger:** ACP reports compaction chunks/statuses, repeats completion during resume, or cannot find a native session.
- **Positive evidence:** `test_compaction_observations.py:51–82` checks merged disclosed patches, one timeline record, one epoch advancement and `retained_context='unknown'`; `:87–98` preserves failed/cancelled/unknown statuses without advancing the epoch. `:103–129` distinguishes child-session observations and replay from parent context changes.
- `test_session_reopen.py:26–37` injects the specific missing-thread error and checks one failed resume/load attempt, disabled capabilities, a readable-history route and a classified unavailable state. `:46–55` preserves unclassified errors unchanged. `:60–68` checks distinct resume/load calls.
- **Limits:** `test_compaction_observations.py:25–29` synthesizes stream events. `test_session_reopen.py:14–20` uses `AsyncMock`; neither is an actual harness cache/session compatibility run.
- **Rebuild requirement:** amendment C disallows inferred retention; amendment E requires ownership/failure comparison independent of ACP location.
- **Smallest boundary:** preserve observer truthfulness and error-classification semantics. Reconnect them to target session/history/epoch records and later demonstrate actual supported harness versions without treating fake capability dictionaries as compatibility evidence.
- **Dependencies:** compaction tests construct `Session` using `Store(..., module='dispatch')` (`:18–21`) and read stored `session_lines` (`:45–48`); resume tests intentionally replace persistence with `save_state`/`note` mocks.

## V6: storage tests are strong legacy evidence and a target-port checklist

**Classification:** correct legacy behavior plus useful verification mechanics, **Adapt** test intent. **Re-engineer or replace** SQLite-specific expectations for target validation.

- **Trigger:** module/map writes share atomic scope, a module schema evolves, or writers race across processes.
- **Positive evidence:** `tests/test_module_tables.py:270–292` verifies rolled-back module writes and a map layer/module row rolling back together. `:295–317` checks upgraded rows, metadata/indexes and backups, explicitly through SQLite.
- `tests/test_feature_storage_boundary.py:42–57` verifies a module operation shares the map's rollback. `:91–121` exports retained feature data while modules are disabled and recovers it after reenablement.
- `tests/test_store_concurrency.py:19–80` drives six processes and checks every write, count and SQLite integrity. `:83–145` checks lock order using an independent SQLite connection while a graph read holds its turn.
- **Limits:** public imports and passing rollback tests say nothing about compatibility with the LadybugDB driver, revised identity rules, materialized ancestry/incidence or snapshot-bound revisions. `test_module_tables.py:257–267` expressly requires SQLite NULL ordering.
- **Rebuild requirement:** amendment B covers all retained state, including settings, prompts, receipts, conversations and event journals.
- **Smallest boundary:** preserve atomicity/concurrency/no-loss scenarios, specify cross-domain transaction units and replay/unknown-outcome behavior, then run them against target persistence and actual callers. Do not preserve SQLite row ordering or filesystem backups as unexamined product requirements.

## V7: preserve negative/empty evidence in shaping, redesign the three views separately

**Classification:** useful mechanics, **Adapt** presentation use; pure shaping routines remain candidates for substantial reuse after their imports are checked.

- **Trigger:** a result contains false, zero, empty values or null, a requested field is unknown, or output is bounded.
- **Positive evidence:** `test_shaping.py:63–72` checks explicit requested values survive both text/data projections; `:94–105` rejects unknown fields before filtering; `:110–119` handles empty result sets without fabricated records; `:124–148` distinguishes null/missing values and full/count from bounded triage.
- **Observed limit:** default triage omits null `unknown` and internal fields in `:75–82`; that is deliberate tested behavior, not proof of an error. Generic triage/full/count are not the owner's local functional, global functional and local knowledge-rich views.
- **Rebuild requirement:** amendment C explicitly requires those three domain presentations and excludes neighbor knowledge from the local knowledge-rich view.
- **Smallest boundary:** reuse value-preserving formatting after domain projections choose their records. Specify completeness/identity indicators and test a selected element with direct neighbors carrying very large knowledge bodies. Do not relabel generic formatting modes as the required domain views.
- **Callers/dependencies:** tests import `metaform.modules.mcp.shaping`; these unit-level assertions do not exercise graph retrieval or backend consistency.

## V8: existing intake tests preserve old choreography, not rebuilt semantic usability

**Classification:** correct legacy behavior conflicting with rebuild goals, **Re-engineer or replace** agent-facing journey. Retain canonical semantic cases.

- **Trigger:** an agent records a functional object with providers, subtypes and receiving-purpose relationships.
- **Observed evidence:** `src/metaform/modules/intake/tests/test_intake.py:78–116` defines its agent-style submission helper as start, individual element creation, separate purpose writes and finish. `:200–210` checks one object-by-object recording against a four-element fixture and durable readback. `:148–168` checks exact rendered intake prompt/source escaping.
- **Rebuild requirement:** amendment A permits redesigning intake implementation/procedural choreography, and amendment C requires compact coherent submissions, revision and semantic readback without database-command choreography.
- **Consequence:** these tests are useful reference cases for Address, receiving ownership and provider relationships; making them pass unchanged would preserve the very interaction costs under review.
- **Smallest boundary:** keep semantic fixtures and outcomes, propose consolidated submission/revision plus explicit readback assertions at the MCP boundary. Preserve exact-source checks where required, but do not use prompt-text equality as a usability demonstration.
- **Dependencies:** helper calls the real CLI fixture and then `Store('timer')`; the test establishes legacy persistence/readback, not target LadybugDB or consolidated MCP behavior.

## Historical evidence kept separate

ECS archive SHA-256 `046eafd31b067e32dee11e5fec08fbfe60c17de7cfba848957721f806de3a9e4`, members `verification/README.md` and `verification/results.json`, state sixteen historical local schema/reference checks. The results explicitly list LadybugDB DDL/Cypher execution, MCP interoperability, ACP harness execution, Bevy/hardware and inference benchmarking as unexecuted. They report an absent Ladybug driver. These are archived author assertions, not commands executed in this review.

The archived next-spec acceptance document is a set of proposed demonstrations, not passed tests. Its AC-14 axial-depth/local-reflex wording requires amendment F's profile distinction and consumer-controlled action semantics. Rechecking schema fixtures alone would still not demonstrate unsigned 65,535 mm virtual data, spherical surround geometry, zone/up-down event angles or general event fallback.

## Proposed acceptance evidence, not tests added or executed

1. Run permitted chassis/template loading and lifecycle scenarios through target persistence without creating SQLite runtime state. Cover module-disabled retained records and public base transitive callers.
2. Demonstrate coherent intake → functional readback → semantic revision, with input/output captures and no storage-operation choreography.
3. Exercise the three domain retrieval presentations and assert local selected knowledge excludes neighbors' bodies.
4. Capture exact delivered text/source version, omitted unchanged bodies, changed deltas and compaction epoch effects. Record retained skills only when observable.
5. Produce many routine ticket/progress changes with zero model calls/bytes while a purposeful unblacklisted peer event reaches its recipient. Test an explicitly blacklisted event independently.
6. Demonstrate supported draft-MCP events and chassis-local fallback with the same event identity, origin, meaning and causation. Include capability/version disagreement and unsupported harnesses.
7. Verify actual Python↔Node streaming, cancellation, session identity, disconnect/reconnect and crash-after-submit unknown outcomes. Run equivalent ACP placement probes before selecting ownership.
8. Validate LadybugDB schema/query/callers/transaction behavior with representative target records, not just driver import or a Cypher parser.
9. Exercise physical 3,500 mm/60-degree sensing separately from virtual unsigned 65,535 mm surround data and the optional conventional virtual profile, without requiring autonomous reactions.

## Read and command ledger

- Commands: `cat` skill/instruction/archive documents; `nl -ba` and selected `head`/`sed` reads; `rg --files` instruction/test inventory; `rg -n` test symbols, imports, capability/event/sensor/backend hints and source consumers; an AST-only Python inventory of test definitions. All ran against the pinned snapshot except installed skill reads.
- Complete test files read: template `test_template.py`, `tests/test_module_data_source.py`, `tests/test_feature_storage_boundary.py`, dispatch `test_informational_delivery.py`, `test_session_reopen.py`, `test_compaction_observations.py`, MCP `test_module_discovery.py`.
- Partial test files read with relevant ranges cited above: `tests/test_base.py`, `test_module_tables.py`, `test_store_concurrency.py`, `test_relay.py`; MCP `test_mcp.py`, `test_upgrade.py`, `test_shaping.py`; memory `test_delivery.py`; intake `test_intake.py`. Other filename/symbol inventory is not represented as a full read.
- Backend/sensor hint search in both test trees found no `Ladybug`, `lbug`, `Kuzu`, `65535` or `surround` match. This bounded text result is not a proof that no indirect target test exists. `subscriptions/listen` matches occur in MCP/cloud tests and are not general event-adapter certification.
- No pytest collection or test execution, CI retrieval, dependency installation, live native harness run, migration, external production workflow or archived-script execution occurred in this pass.
- No independent conclusion relies on another reviewer's report. Cross-review challenges will be a separate document after coordination.
