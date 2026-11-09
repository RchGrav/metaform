# Reviewer 3: Context delivery and continuity

Independent first pass frozen on 2026-10-29. No other reviewer report was read before this pass. This report changes no implementation or prompt source.

## Basis and method

- Reviewed implementation: remote `main`, `fceef55a2fb6bd9bf5f8a46310e1af84276fa9f9`, from `/tmp/metaform-review-20261029-fceef55a`.
- Original checkout: `/home/rich/metaform`, local `main` at `261a1cb7172159b4354308a423028a86ffc179f3`, initially clean, one local commit ahead and two remote commits behind. The coordinator verified the remote ref and made the isolated snapshot.
- Governing source: the owner's amendments A–F, ECS packet, and archived specification with amendments taking precedence. Root AGENTS.md, CLAUDE.md and README.md were consulted. No nested instruction file was found in the snapshot's instruction-file inventory.
- Skills read: `metaform-dev/SKILL.md`, installed `bmad-review/SKILL.md`, its `customize.toml`, adversarial lens and edge-case lens. Review lenses were applied sequentially within this reviewer to preserve the seven-agent concurrency bound. The owner's no-quota instruction overrides the adversarial lens's minimum count.
- `_bmad/` is absent in the source snapshot. Customization falls back to the installed TOML as the review skill permits. No project-context.md was found in the source inventory.
- Source paths below are relative to the pinned commit. ECS references denote members of `ecs/Inference-Metaform-ECS-Terminology-Review.zip`, SHA-256 `046eafd31b067e32dee11e5fec08fbfe60c17de7cfba848957721f806de3a9e4`, extracted under `review-sources/ecs/`. Archived-spec references denote members under `metaform-specifications/` in the specification ZIP, SHA-256 `0ed29b853d95f01f4bd545c7fb68380962abce3831f4f31d439ae3a13963bcb9`.
- Parent graph lookup: project `home-rich-metaform`, generation `2026-10-29T06:06:33Z`, reported ready and no recorded coverage issue for the six queried core paths. That index describes the local checkout, not the remote snapshot. All material conclusions here use direct pinned-source reads instead.

## Actual payload paths

### First prompt and subsequent turns

`src/metaform/modules/dispatch/runner.py:4537` `Session.guidance` enters a fresh registry scope, then `current_guidance` resolves rules/catalog, communication, the assignment's pinned role snapshot or current role, effective context and the memory instruction (`:4542–4598`). `prepare_agent_context` selects due components. Only actual component text absent from the supplied prompt is prepended (`:4599–4604`). Snapshot capture checks that each rendered body occurs in the outgoing text (`:4605–4609`).

`Session.prompted` uses guidance only for a fresh, unspoken, non-resumed conversation (`src/metaform/modules/dispatch/runner.py:4917–4923`). It appends changed-role references and memory-change references to the next already scheduled turn (`:4931–4946`). The transport-bound payload is explicitly `[acp.text_block(text), *beside]`, plus attached resource-link blocks, sent with `conn.prompt(session_id=..., prompt=blocks)` (`:4954–4961`). Attached links are descriptors, not evidence that their resource bodies were read.

`Session.observe` invokes `context_delivered` only after an outgoing `session/prompt` transport observation for the current native session (`src/metaform/modules/dispatch/runner.py:1943–1949`). `context_delivered` records the captured epoch/components and actual rendered body, source and selected version with channel `acp_prompt` (`:4654–4669`). It then emits `prompt.sent` through `carried`, which contains metadata, not an instruction injection (`:4734–4751`).

### MCP resources, commands and discovery

`src/metaform/modules/mcp/server.py:2236` `read_resource_text` resolves a resource, prepares components, records body receipts with `mcp_resource`, and returns the text (`:2267–2278`). `discovery_delivery` maintains separate component names for module/tool discovery (`:1468–1476`). The resource handler constructs `ReadResourceResult` only afterwards (`:3194–3207`).

Memory bodies use queued snapshots and `_commit_response`, which acknowledges a component only when its delivered value survives result shaping (`src/metaform/modules/mcp/server.py:1683–1697`). This is stronger than acknowledging all resolved bodies. It still establishes server-side response construction, not a host-model observation. It does not equal the ACP outgoing-send boundary.

### Stored diagnostics

`agents.record` writes `prompt.sent` into the agents module's `sent` table (`src/metaform/modules/agents/__init__.py:547–558`). `agents.sent` reconstructs the recorded effective instruction manifest and explicitly labels native instructions and semantic retention as unknown (`:397–424`). Reading those records or editing a prompt source does not establish delivery to any running model.

## Candidate assessments

### C3-1. Preserve exact rendered-source identity and accepted-send capture

**Classification: Adapt. Useful mechanics behind a new persistence/harness boundary.**

- Trigger: a selected prompt edit is malformed, a trial overrides a source, or a selected version changes between preparation and transmission.
- Observed: `prompt_files.component` hashes the rendered text (`src/metaform/prompt_files.py:638–645`). `resolve/_resolved` distinguish actual from selected version, shipped identity, trial path and fallback (`:648–720`). `Session.current_guidance` captures text present in the eventual prompt and `context_delivered` uses that snapshot rather than resolving again (`src/metaform/modules/dispatch/runner.py:4605–4609`, `:4654–4669`).
- Requirement: amendment C requires source/version identity and truthful once-per-epoch delivery. ECS technical `03-technical-specification.md:35–41` separates immutable snapshot descriptors from mutable runtime revisions. Its `:664` delivery contract includes the actual digest/revision and channel.
- Consequence: keep these source-resolution semantics and the outgoing-send observation. Do not reuse the whole prompt store unchanged or turn `prompt.sent` diagnostics into model context.
- Smallest boundary: an immutable resolved-component record plus a runtime ledger that accepts a captured body/version only at the adapter's declared delivery boundary. Preserve selected-versus-actual fallback evidence and renderer bindings.
- Callers/dependencies: role resolution `src/metaform/modules/agents/roles.py:175–211`, first-turn guidance, MCP rule/role/memory resources, skills' selected procedures. `prompt_files.resolve` reaches `src/metaform/data/prompts.py`, explicitly a SQLite prompt store (`src/metaform/data/prompts.py:1–9`, `:15–24`, `:47–78`). Receipt writes reach `Store.tables`, whose opener returns `sqlite3.Connection` (`src/metaform/data/store.py:400–414`).
- Tests read: `src/metaform/modules/agents/tests/test_authored_roles.py:248–281` asserts selected/fallback/trial identity, captured outgoing snapshot and unknown native retention. `src/metaform/modules/dispatch/tests/test_orchestration_runtime.py:230–239` checks a fake ACP recipient receives shared role text once and its receipt carries that exact body. These are source-inspected legacy tests, not new backend or real-harness proof.

### C3-2. Preserve epoch/body deduplication and revision references, replace their storage realization

**Classification: Adapt. Positive reuse evidence.**

- Trigger: repeated context access, duplicate bodies under aliases, A → B → A reactivation, a late acceptance after compaction, or a role revision after a notice was prepared.
- Observed: `RoleService.prepare` recalculates actual-body fingerprints, deduplicates by epoch and sends a reference when an already delivered body becomes active again (`src/metaform/modules/agents/roles.py:248–299`). `record` rejects stale epochs and retains delivered-body history (`:358–400`). `changes` sends references only for previously delivered components, and `delivered_changes` records notices separately from body receipts (`:301–356`).
- Requirement: amendment C and archived `lifecycle-and-delivery.md:13–17` require unchanged material once per epoch, deltas and distinct delivery states. ECS technical `:279–281` and `:678–690` preserve explicit versions, source reads and unknown comprehension.
- Consequence: retain the prepare/accept separation, stale-epoch guard and restore-reference behavior. The SQL module-table abstraction is not storage-independent evidence.
- Smallest boundary: model `context`, `body delivery` and `change notice` as revisioned runtime records with transactionally checked epoch and content identity. Keep notice acceptance independent from body acceptance.
- Callers/dependencies: public `prepare_agent_context`/`record_agent_context`, ACP and MCP paths above. Tables `contexts`, `receipts`, `delivered_text`, `change_notices` and `context_checks` are declared in `src/metaform/modules/agents/roles.py:28–45`; all reach `Store.tables` and `TableTx` SQL (`src/metaform/data/tables.py:1220–1245`). `src/metaform/shown.py:25–31`, `:60–71` separately stores named-session discovery in the home SQLite chassis DB. Both persistence paths must move.
- Tests read: `src/metaform/modules/agents/tests/test_authored_roles.py:171–190` covers body aliases and epoch reset; `:193–217` proves a missing marker neither changes the epoch nor invalidates receipts; `:401–426` proves old notice acceptance cannot erase a newer revision and a reference cannot acknowledge a body.

### C3-3. Preserve consumed-memory delta mechanics, adapt topology and storage

**Classification: Adapt. Useful mechanics, with a different graph/projection implementation.**

- Trigger: an agent read one memory, another participant changes/deletes it, or an unrelated branch changes during the same context epoch.
- Observed: `src/metaform/modules/memory/delivery.py:67–78` gives canonical entity/relation bodies stable content identities. `changed` stores entry revisions and withdrawals, excludes the writing session and coalesces references only for encountered entries (`:102–144`). `prepare` separates body eligibility from acknowledgment and carries an entry revision captured with its body (`:209–236`). `queue` delays MCP acknowledgment until response shaping (`:239–248`). Discovery titles/counts leave body receipts untouched (`src/metaform/modules/memory/__init__.py:1075–1092`).
- Requirement: amendment C's coherent local knowledge view and delta delivery. Amendment D forbids purposeless live activity flooding, while allowing deliberate context and communication. ECS technical `:220–222` retains attachment reasons and separates namespace ancestry from functional incidence.
- Consequence: retain reference coalescing, withdrawals, writer exclusion and same-snapshot revision capture. Do not retain legacy memory-table joins or infer that an encounter/count establishes comprehension.
- Smallest boundary: publish changed item/revision/affected functional entry identity after the write, then resolve only the recipient's consumed-item deltas against its context epoch. Use target `ContextItem` attachments and runtime delivery records.
- Callers/dependencies: `memory._delivered`, `read_graph`, `read_unread`, `open_nodes`, `node_read`, MCP shaping and next-turn provider `agent.context.changes`; `src/metaform/modules/memory/delivery.py:29–47` defines SQL runtime tables. `revision` creates `Store(project,module='memory')` (`:194–198`), so even watcher reads transitively use legacy storage.
- Tests read: `src/metaform/modules/memory/tests/test_delivery.py:179–229` protects count/shaped-away and nested transport identity; `:561–584` protects coalesced correction/deletion references and late acceptance; `:587–612` protects own-write/unrelated exclusion and reread suppression. No claim is made that these tests establish LadybugDB projection correctness.

### C3-4. Distinguish MCP response preparation from actual harness delivery

**Classification: Adapt. Boundary evidence gap, not a proven host-retention defect.**

- Trigger: resource response construction succeeds and records a receipt, then the response is lost, rejected or never included in the model's context.
- Observed: `discovery_delivery` records at `src/metaform/modules/mcp/server.py:1475`; role/rule/memory/glossary resource preparation records at `:2272–2273`; `_commit_response` records after shaping at `:1696–1697`. The result object is constructed later at `:3207`. The inspected paths have no host-model acknowledgment corresponding to the ACP observer at `src/metaform/modules/dispatch/runner.py:1943–1949`.
- Requirement: amendment C forbids equating receipt with comprehension or unobservable retention. ECS technical `:680–682` distinguishes discovery, body delivery, skill loading and changed-since-delivery.
- Consequence: preserve truthful observations at each boundary. Server-produced content may support protocol delivery bookkeeping, but the rebuild must not label it host injection, skill loading or comprehension. This report does not assert that MCP offers a universal model-injection acknowledgment.
- Smallest boundary: record response-prepared/server-emitted/harness-injected states only where observable, with source/version/transport identity and an explicit unknown state. Retain revision-addressed recovery reads when the harness cannot confirm retention.
- Callers/dependencies: resources/read and catalog/tool results, roles ledger, `shown` chassis ledger, MCP session handles and response shaping. All durable receipts currently reach SQLite as described in C3-2.
- Tests read: `src/metaform/modules/memory/tests/test_delivery.py:179–229` tests shaping and identity, not transport loss after return. `src/metaform/modules/mcp/tests/test_mcp_skills.py:118–167` exercises stdio initialize/read/call and discovery with test clients, not model injection. The narrower inspection result is that these read tests do not establish the later harness boundary. No repository-wide absence claim is made.

### C3-5. Preserve compaction observations and resume history, engineer retained skills and logical handoff

**Classification: Adapt for observations/resume. Re-engineer the target retention/handoff boundary.**

- Trigger: ACP reports completed compaction, replays old compaction history on load, loses a native rollout, or reopens a useful completed worker for related work.
- Observed: `Session.observe_compaction` preserves disclosed lifecycle/summary patches, distinguishes child sessions and advances once only for a newly observed parent completion (`src/metaform/modules/dispatch/runner.py:1982–2026`). `keep_compaction` stores diagnostic state without creating a turn (`:2028–2052`). `compacted` emits `session.compacted` with retained context unknown and makes reads eligible in the new epoch (`:2054–2072`). `reopen` selects advertised resume/load and preserves history on the specific missing-rollout failure (`:4252–4289`). `continue_thread` restores the same runner identity and stored thread state (`:4291–4329`).
- Observed retention limit: `skills.load` returns metadata, current procedure and libraries (`src/metaform/skills.py:126–130`); `server.run_skills` forwards it (`src/metaform/modules/mcp/server.py:563–579`). These functions take no context/epoch and maintain no learned-skill set. `Session.prompted` intentionally avoids bulk guidance replay after compaction (`src/metaform/modules/dispatch/runner.py:4917–4946`). This supports on-demand grounding, not proof of ECS retained-skill-segment restoration.
- Requirement: amendment C separates discovery, resource delivery, skill loading and retention. ECS technical `:321`, `:339–352`, `:680–684` requires retained skill versions, observable loading and explicit handoff references, while recording unsupported harness limits. Archived `lifecycle-and-delivery.md:15–17` preserves approximately 50% self-handoff and later enforcement around 65%, using measured harness capacity. No universal five-minute expiry is allowed.
- Consequence: keep compaction patch/replay handling, truthful unknowns, capability-driven resume and readable historical threads. Add an explicit logical agent/context identity and retained-skill contract at whichever runtime owns the harness. Do not choose ACP placement by this existing Python implementation.
- Smallest boundary: separate logical agent ID, native session ID, context ID/epoch and work assignment. An adapter reports actual loaded skill digests and can restore an explicitly supported segment after compaction. A successor context gets work/decision/revision/event-cursor/worktree/skill references, not an assumed copy of all predecessor bodies. Capacity-based handoff requires actual harness measurements and the settled thresholds, not invented ones.
- Dormant reuse evidence: `src/metaform/modules/orchestration/episodes.py:34–94` records explicit workstream continuity and binding history. `Orchestration.episode` and `inherit_runtime` preserve declared related work and an advertised unchanged runtime choice (`src/metaform/modules/orchestration/state.py:899–949`). These are useful continuity mechanics, not evidence of a measured cache-economics selection policy or complete logical identity/handoff model.
- Callers/dependencies: `session.compacted` subscriber `src/metaform/modules/agents/roles.py:466–469`; SQL `agent_sessions`/`session_lines`; agents epoch ledger; orchestration `episodes`, `episode_work`, `binding_history` (`src/metaform/modules/orchestration/episodes.py:17–30`); home run-file markers and prompt store. No SQLite exception is implied.
- Tests read: `src/metaform/modules/dispatch/tests/test_compaction_observations.py:51–129` protects patching, exactly-once epoch, replay and child isolation. `test_session_reopen.py:14–68` uses mocked ACP to test resume/load and known missing rollout, not a live Codex session. `test_orchestration_transport.py:417–463` protects no unsolicited bulk replay. `test_orchestration_runtime.py:396–426` uses fake ACP/MCP and proves on-demand re-grounding. `src/metaform/modules/orchestration/tests/test_episodes.py:30–85` proves session rebinding and historical results/return routes. None is represented as real retained-model-context evidence.

### C3-6. Replace fixed peer-delivery policy while retaining compact messages and duplicate protection

**Classification: Re-engineer policy. Adapt transport/receipt mechanics. Correct legacy behavior conflicts with amendment D.**

- Trigger: an agent deliberately sends a useful informational peer message, or a new event producer uses a kind outside the hardcoded delivery inventory.
- Observed: `src/metaform/modules/dispatch/orchestration.py:477–505` `actionable` rejects kinds outside a fixed list except special user-direction/board paths. Result, blocker and recommendation delivery then depends on assignment/GC/return ownership (`:506–577`). `Session.peer_note` consults that policy (`src/metaform/modules/dispatch/runner.py:4410–4412`) and keeps a disallowed delivery as `record_only` (`:4481–4483`). Thus a deliberately sent plain peer message can be stored but cause no message turn. Informational-delivery tests explicitly enforce this behavior.
- Requirement: amendment D permits purposeful messages, assignments, peer communication and reasoned orchestration, rejects continual activity mirroring, and explicitly prohibits an inferred hierarchy or event allowlist. The dynamic blacklist remains the governing restriction model. This is not permission to flood routine state updates.
- Consequence: do not carry `actionable` or the no-informational-turn assertion forward as a universal event adapter. The useful no-progress-mirroring guarantee survives, but its enforcement must occur at event-production/subscription and explicit delivery intent rather than a fixed kind inventory.
- Smallest boundary: producers distinguish stored diagnostics from deliberately addressed deliveries. Preserve meaning/origin and explicit recipient intent through the general draft-MCP/chassis-local adapter. Apply actual capability and configured dynamic blacklist. Keep cancellation/withdrawal/replay revalidation and duplicate-delivery protection, without turning assignment relationships into general permission.
- Positive mechanics: `peering.line` emits a bounded sender/task/message line with an explicit full-read route (`src/metaform/modules/dispatch/peering.py:595–609`); `peer_note` keeps the original envelope in the thread and suppresses duplicate queued IDs (`src/metaform/modules/dispatch/runner.py:4424–4467`). `turn` coalesces pending peer bursts (`:4766–4783`). These can serve the redesigned interface without becoming a content allowlist.
- Callers/dependencies: `peering.send` stores sender/recipient copies and forwards to live runners or pending assignments (`src/metaform/modules/dispatch/peering.py:428–480`). Receipt/replay uses SQL session lines (`src/metaform/modules/dispatch/runner.py:4686–4714`), and `signals.collect` persists raw signals separately (`src/metaform/modules/dispatch/signals.py:249–266`). Target runtime records must replace both store paths.
- Tests read: `src/metaform/modules/dispatch/tests/test_informational_delivery.py:80–99` requires no prompt/piggyback for all enumerated plain peer/informational kinds; `:129–181` checks owned results, invalidated queue requests and surviving questions/blockers; `:184–203` checks deliberate user directions versus project updates. These tests protect the present policy, not rebuild compliance. Retain the zero-routine-update-transport assertion while revise the deliberate-peer-message scenario to the owner's contract.

### C3-7. Re-engineer context projection independently from namespace traversal and command schema

**Classification: Re-engineer projection contract. Adapt explicit-scope and layer-selection mechanics.**

- Trigger: entering a receiving element with several provider Joins, requesting a local knowledge-rich view, or requesting the global functional map without ancillary layers.
- Observed: `Store.context` delegates to the legacy read transaction/resolver (`src/metaform/data/store.py:563–568`). `reads.context` collects applying properties from namespace prefixes, then visible descendants and scoped knowledge (`src/metaform/data/reads.py:261–292`). `scoped_knowledge` expands an explicitly linked subtree with instruction-only inheritance (`:296–319`). First-turn `current_guidance` serializes applying properties and knowledge as `map:effective_context` (`src/metaform/modules/dispatch/runner.py:4575–4581`). This is real payload generation, but it is not the ECS place envelope with snapshot/runtime versions, attachment reasons and incident-Join topology.
- Requirement: amendment C keeps namespace ancestry, functional relationships and reasoning distinct, and requires all three retrieval presentations with neighbors' knowledge excluded. ECS technical `:220–222`, `:266–281` defines functional incidence, attachment provenance, revision-bound paging and native descriptor preservation.
- Consequence: reuse layer/mask/scope behavior as acceptance examples, not the old SQL traversal or map_context shape as the final MCP contract. Keep local functional/global functional/local knowledge-rich response selection explicit.
- Smallest boundary: a target projector takes snapshot, Address, layer selection and requested presentation, then returns source/version descriptors and bounded direct functional relationships. Automatic orientation can be deduplicated; explicit source/version body reads remain available and truthful about continuation. Keep discovery and skill-loading ledgers separate.
- Callers/dependencies: first-turn guidance, `map_context`, map node reads, memory hooks and `Store._read` (`src/metaform/data/store.py:127–134`). The dependency chain reaches legacy `Tx`, cached base rows/resolver and SQL sessions; replacing only an import would preserve the old data model.
- Tests read: `tests/test_scoped_knowledge.py:16–52` asserts inherited instructions, local evidence exclusion, sibling isolation, masks, hidden layers and explicit empty selection through CLI/MCP. It does not assert the three target presentations or ECS snapshot-based incidence. This is a bounded claim about that test, not an assertion that no related test exists.

## Decisions still requiring discussion or evidence

- ACP-in-Python versus ACP-in-Node remains open. Either placement must own a clearly declared context/session/stream/cancellation/recovery boundary, while sharing the same truthful delivery/compaction semantics. Existing Python ownership proves historical implementation, not the rebuild choice.
- A native harness's actual retained-skill observability and projection capability must be verified at its supported capability/version. The current fake ACP and MCP client tests do not establish those capabilities. Codex is the owner's current supporting harness, not inferred from a process label.
- Dormant selection needs measurements of model/harness cache economics and retained-context utility. Explicit episode reuse is implemented. The inspected code does not establish the target selection economics or intended threshold behavior.
- Keep the settled LadybugDB backend and all six owner amendments. These are not open questions. Recovery of September integration is outside this reviewer's ownership.

## Verification ledger

**Tests executed: none.** Direct source and test inspection resolved this review's implementation questions without launching models, production agents, live workflows, migrations or browser checks.

**Test isolation inspected:** `conftest.py:11–16` assigns a temporary process-wide home; `:25–43` installs fake agent commands and Full Auto off for ordinary tests; `:46–69` gives each test fresh home/session isolation and removes inference billing credentials. `pyproject.toml` test options select chassis and module tests, use xdist by default and exclude `browser`. An eventual focused command should use `uv run pytest -n 0 <selected paths>`. No such command was run here.

**Test sources read:** the exact ranges cited above in `test_authored_roles.py`, `test_delivery.py`, `test_informational_delivery.py`, `test_compaction_observations.py`, `test_session_reopen.py`, `test_orchestration_transport.py`, `test_orchestration_runtime.py`, `test_mcp_skills.py`, `test_episodes.py`, `test_scoped_knowledge.py`. `test_auto_delivery.py:1–152` was also inspected: its “delivery” concerns feature commits/landing, not context injection, so it contributes no context-retention claim.

**Commands used:** read-only `rg --files`, `rg -n`, `wc -l`, `cat`, and `nl -ba ... | sed -n ...` over root instructions, installed skills, archive members and the pinned paths. Some broad searches returned truncated output and were followed by smaller exact source reads for material findings. Missing guessed `mcp/resources.py`, `mcp/delivery.py`, `data/context.py`, and `data/tx.py` paths were corrected by file/symbol searches. No absence finding relies on those failed path guesses. Only this report was written.

**Archived results:** ECS `verification/results.json` and the archive's limited verification record are historical artifacts, not results of this review. No claim of new LadybugDB, Node.js, ACP, draft-MCP-event or real-model integration is made.

**Proposed acceptance checks, not executed:** preserve exact actual/selected version fallback at an adapter capture; reject stale-epoch acceptance; distinguish discovery/body/skill loading; retain skill digests across movement with supported compaction recovery; resume a dormant native session or record unavailable context without losing history; deliver an intentional peer message across either event transport while routine progress emits zero model turns; verify all three presentation shapes against the new graph and retained runtime state.

The reviewed foundations support extraction and adaptation. They do not establish that the rebuild is implemented or implementation-ready.
