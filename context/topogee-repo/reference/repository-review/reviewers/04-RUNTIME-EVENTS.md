# Reviewer 4: Runtime, events, harness adapters and Python–Node

Independent first pass, frozen 2026-10-29. No other reviewer findings were read before this report was written.
Source revision: `fceef55a2fb6bd9bf5f8a46310e1af84276fa9f9` (verified remote `main`), read from `/tmp/metaform-review-20261029-fceef55a`.
The actual checkout remains at `261a1cb7172159b4354308a423028a86ffc179f3`. All implementation citations below refer to the pinned source revision, not that checkout.

## Method and authority

Read the Metaform development skill and BMAD Review skill, customization and adversarial/edge-case lens instructions before reviewing. Applied adversarial review and path tracing sequentially within this assigned scope. The owner's no-quota direction overrides the adversarial lens's minimum count. The project `_bmad` resolver is absent, so installed `customize.toml` defaults supplied customization. No project-context file was found by the coordinator's initial instruction scan. No subagents were started by this reviewer.

Authority: owner amendments A–F over the archived rebuild specification, with ECS as starting ground truth. The active legacy requirements establish legacy intent, not automatic rebuild requirements. The archive's old instruction to avoid exploratory event methods is source material superseded by amendment D.

Interpretation used: a local event bus, MCP resource notification, protocol event delivery, host scheduling and actual model injection are distinct observable boundaries. A transport receipt is not comprehension. A Node.js-backed external ACP adapter is real JavaScript runtime use, but does not establish the rebuild's own Python–Node service contract.

## Candidate decisions

### R4-01: Keep the chassis event mechanics, adapt their dependencies and event contract

- Classification: **Adapt**. Useful legacy mechanics, with a rebuild persistence/interface mismatch. No legacy defect established.
- Trigger: a module commits a change and another module or process must react without polling.
- Observed: `events.publish` rejects use inside a running event loop at `src/metaform/events.py:23–31`. `publish_async` awaits async handlers and moves synchronous handlers to a worker thread at `:50–74`. Both isolate subscriber failures, copy payloads for subscribers, and return delivery outcomes. `listen` delegates cross-process delivery at `:77–81`.
- Positive evidence: the existing bus already separates producer topics from subscribers and prevents a synchronous publisher from blocking an async loop. The outcome list distinguishes completed, failed and cancelled subscriber calls. Preserve these behaviors.
- Dependencies/callers: `events.py:19–20,34–41` imports loader, relay, Context and invocation machinery and builds module Contexts. `loader.enabled` is `src/metaform/loader.py:344`, Context construction is `src/metaform/context.py:31`, and Context/Store/home ultimately reach SQLite (`src/metaform/data/store.py:20,400`, `src/metaform/data/tables.py:21,28`, `src/metaform/home.py:20,36`). The whole file is therefore not proven backend-independent.
- Requirement: A permits reviewed chassis reuse, B requires new backend/model across retained state, D requires general purposeful events and capability-selected delivery.
- Smallest boundary: retain subscription/invocation and cancellation semantics behind a backend-neutral runtime Context. Supply committed domain-change descriptions from the LadybugDB service. Add the general event adapter downstream rather than making producers know harness names.
- Tests read: `tests/test_map_changed.py:58–73` checks read silence, write notification and one notification for one command, using the actual CLI and legacy map. `src/metaform/modules/dispatch/tests/test_orchestration_transport.py:226–260` checks 350 unrelated changes produce no reads or scheduled work. These protect useful behavior, not LadybugDB integration.

### R4-02: Replace SQLite write observation, preserve post-commit concern aggregation

- Classification: **Re-engineer or replace** for database observation, **Adapt** for aggregation. Correct legacy behavior conflicts with new storage.
- Trigger: a write must produce an attributable change notice only after commitment.
- Observed: `src/metaform/changes.py:13,34,42–55` uses SQLite action constants and `Connection.set_authorizer`. `unwatched`/`changed` use `total_changes` at `:59–80`. `note` holds project/base/table/sequence/concern state at `:83–95`. `announced` captures one invocation separately at `:137–160`, and `_fire` creates `map.changed` at `:188–206`.
- Requirement: B rules out a driver-only swap and silent SQLite runtime exceptions. D requires event meaning/origin across transports.
- Consequence: table-authorizer observation cannot be reused unchanged. Table names such as `work` and `session_lines` are current persistence details, not the rebuilt semantic event API.
- Smallest boundary: the new writer reports a committed change set with domain identities, source revision and affected targets. Keep per-call isolation and concern merging as mechanics. Associate journal append and source mutation with the specified publication transaction where required.
- Callers/storage: Store/TableTx and home writes call the change recorder. CLI/MCP invoke `events.announce`; MCP does so at `src/metaform/modules/mcp/server.py:2996–2998`. Events then reach resource watchers and dispatch/orchestration subscribers. Direct and transitive storage must move together.
- Tests read: `tests/test_map_changed.py:92–104` covers project-level module-table memory changes. `test_orchestration_transport.py:252–260` covers mixed-table concern loss and delivery acknowledgments. Neither verifies LadybugDB commit/failure ordering.

### R4-03: Existing cross-process relay is useful local IPC, not a durable general event service

- Classification: **Adapt**, with a new durable event boundary. Useful mechanics, no demonstrated legacy defect.
- Trigger: one process publishes while a different chassis process listens, or a listener disconnects.
- Observed: `src/metaform/relay.py:25` restricts delivery to `map.changed`. `Listener` creates a loopback socket and token-protected private registration at `:36–52`; it blocks on socket accept without a polling timer at `:54–69`. `take` acknowledges receipt before invoking the handler at `:71–87`. `deliver` skips the producer PID at `:113–139`, and removes a refused stale listener record at `:143–145`.
- Requirement: D calls for general events and local fallback. ECS `03-technical-specification.md:610–637` requires durable identities, reconnect cursors and explicit uncertain outcomes. B excludes an incidental SQLite event journal.
- Consequence: current acknowledgment means the listener accepted a payload, not that a handler completed or a model received it. There is no persisted replay cursor in this relay path. Its filesystem records are ephemeral endpoints, not durable runtime history.
- Smallest boundary: preserve wakeup-based socket lifecycle/token handling for chassis-local transport where appropriate. Route durable events through the shared LadybugDB RuntimeRecord journal and delivery ledger. Replay from journal identity/cursor after reconnect; do not convert ephemeral IPC acknowledgments into execution claims.
- Callers/storage: `events.publish[_async]` call `relay.deliver`; `events.listen` calls `relay.listen`. `relay` uses `home.home` and file utilities, importing the SQLite-backed home module even though its own registrations are files. Extract filesystem support or adapt home access before calling it unchanged reuse.
- Tests inspected: the dispatch/MCP watcher tests above observe relay consumers. This reviewer did not independently inventory every relay-specific test, so no repository-wide absence claim is made.

### R4-04: Retain version-aware notification mechanics, engineer draft MCP Events separately

- Classification: **Adapt** for existing notifications, **Re-engineer or replace** for the general domain-event surface. Correct legacy behavior is narrower than the rebuild.
- Trigger: a client needs a catalog/resource invalidation versus an agent needs a purposeful upstream event.
- Observed: `src/metaform/modules/mcp/server.py:2631–2638,2751–2757` creates the SDK subscription bus with tool/prompt/resource changes and ResourceUpdated. `conn_key` branches by negotiated protocol at `:2795–2802`. `listen` watches explicitly subscribed URIs at `:3222–3230`. `Watch` intentionally sends resource-update hints, never item bodies, at `:3413–3419,3525–3530`.
- Positive evidence: the watcher filters projects/tables before reads at `:3496–3511` and coalesces pending checks at `:3533–3565`. This is useful event-driven invalidation and should survive through new projection/version APIs.
- Search evidence: `rg -n 'events/list|events/subscribe|events/stream|notifications/events/event' src tests` found no matching current-source/test references in the pinned snapshot. That supports the narrower finding that the inspected implementation has no named draft-Events method path. It is not a live protocol interoperability test.
- Requirement: D expressly requires supported draft MCP Events where available and chassis-local fallback for other harnesses. The ECS baseline says at `03-technical-specification.md:413` it does not depend on exploratory proposal methods; that prescription must be amended.
- Smallest boundary: expose an event-adapter contract whose input is a canonical event plus destination and negotiated capability evidence. Select the supported draft event mode/revision if available. Otherwise deliver that same event through a local message/event endpoint. Keep resource invalidation for its existing discovery/read purpose. Producers remain independent of either transport.
- Dependencies/callers: `Watch._number` constructs Store at `server.py:3435–3440`; `_memory_revision` calls module providers at `:3442–3450`. This watcher must read the new projection/revision boundary, not old item numbering and SQLite tables. `mcp/transport.py` relays SDK wire messages, not domain events.
- Tests read: `src/metaform/modules/mcp/tests/test_mcp.py:2080–2109` launches the real Python MCP server and checks tool-list notifications on the July subscription wire. `:2901–2941` checks unrelated events produce zero watched-node reads. These establish existing notification mechanics only.

### R4-05: Keep hot-replacement safety mechanics behind a redesigned backend boundary

- Classification: **Adapt**. Useful legacy transport mechanics. No LadybugDB or Python–Node integration claim.
- Trigger: a long-lived stdio MCP connection encounters source/schema version changes while a write is already in flight.
- Observed: `src/metaform/modules/mcp/transport.py:79–94` checks staleness only for tool calls and avoids replacement while other calls are pending. `:96–123` verifies successor readiness and preserves the opening protocol era. `:151–165` waits for cancellation settlement instead of guessing completion from a cancellation notification. `:33` imports `NewerStore` from the legacy data layer.
- Requirement: preserve source/version identity and uncertain outcomes, but accommodate the different backend/model under B. An existing private retry marker is not an idempotency strategy for replaying committed rebuild changes.
- Smallest boundary: keep orderly pipe ownership, readiness check, correlation and wait-for-settlement behavior. Replace the SQLite-schema-specific refusal trigger with explicit runtime/service compatibility. Do not replay operations whose committed outcome is uncertain.
- Tests read: `src/metaform/modules/mcp/tests/test_upgrade.py:133–175` checks a previously committed write occurs once through replacement; `:178–192` checks a July subscription remains usable; `:195–235` checks cancelled active/buffered calls settle before replacement. Assertions query SQLite directly. They cannot certify the new service or durable event delivery.

### R4-06: ACP capability/version helpers are strong extraction candidates, full runner is not

- Classification: **Reuse substantially unchanged** for the bounded pure parsing helpers `proxy.version_of`, `agent_capabilities`, `session_group`, `lists_sessions`, `takes_up`, `mcp_over_acp`; **Adapt** for Chain/McpProvider/lifecycle integration.
- Trigger: an actual peer advertises ACP v1 versus draft v2, list/resume support or MCP-over-ACP.
- Observed: `src/metaform/modules/dispatch/proxy.py:48–115` chooses fields by negotiated version and supports boolean/object capability markers. These helpers read dictionaries and have no storage calls. Their callers are `Served.initialize` at `src/metaform/modules/dispatch/serve.py:641–666`. Transitive runtime calls remain in the caller, not inside the bounded helper candidates.
- Positive evidence: Chain maintains hop-local request IDs at `proxy.py:175–210`; cancellation is reissued with mapped IDs at `:199–204`. McpProvider bounds active requests at `:278–300`, maps cancellation at `:310–324`, routes notifications only to their owning request at `:326–363`, and resolves pending requests on pipe failure at `:364–367`.
- Requirement: E leaves ACP placement open and asks for session/stream/cancel/recovery ownership evidence. D selects transports by real capability/version, not harness name.
- Smallest boundary: extract the tested parsers as version-profile utilities with explicit supported revisions. Retain correlation/cancellation semantics in whichever process owns the ACP connection. Replace assumptions tied to the specific MCP revision (`proxy.py:40`) when the selected draft profile requires it.
- Tests read: `src/metaform/modules/dispatch/tests/test_dispatch.py:5020–5058` manually simulates conductor proxy/MCP-over-ACP exchange and asserts ID mapping and Metaform tool readback. `:5123–5153` uses `FAKE_ACP_V2` and asserts message upserts and idle state. The reference conductor test at `:5190–5206` is conditional on `METAFORM_ACP_CONDUCTOR` and still uses the fake agent. None was executed in this review.

### R4-07: Preserve asynchronous sessions/cancellation, replace runtime persistence and hardcoded delivery policy

- Classification: **Adapt** lifecycle mechanics, **Re-engineer or replace** persistence and the general delivery-policy boundary. Correct legacy behavior differs from the rebuild.
- Trigger: a busy session receives another turn, cancellation arrives, or an addressed message uses a kind outside the old orchestration vocabulary.
- Observed mechanics: `dispatch/serve.py:106–123` stores per-session locks, cancellation generations and queue state. `:219–278` moves blocking pipe IO to dedicated threads, `:391–409` uses correlated futures, and `:416–443` cleans up pending operations/providers/processes. Runner constructs async subprocess pipes and ACP connection at `runner.py:4173–4184`; `interrupt` serializes cancellation and lets the turn response own completion at `:5337–5351`.
- Storage: `serve.Record` has a separate ordered write backlog at `:1225–1260`. Its records use `Store.tables`, `agent_sessions` and `session_lines` at `:1300–1321`. Runner duplicate-delivery lookups likewise use `session_lines` at `runner.py:4427–4435`. Reusing an ACP socket abstraction does not preserve these transitive dependencies automatically.
- Delivery mismatch: `dispatch/orchestration.py:477–505` permits only named current request kinds, then validates managed assignment/return-to relationships at `:506–577`. `runner.peer_note` calls that gate at `:4410–4412`; a false result records without delivery at `:4481–4483`. `inbox_add` drops every non-waking entry at `:3971–3986`. These are existing policy decisions, not a model of the required general fallback.
- Requirement: D permits purposeful messages/events and forbids importing an inferred hierarchy or event allowlist. Preserve the explicit dynamic blacklist, not an invented mandatory GC/reviewer chain. Preserve the useful no-routine-flood behavior independently.
- Smallest boundary: separate addressed delivery and wake scheduling from the legacy managed-assignment predicates. Apply explicit configured blacklist restrictions, destination/subscription and reasoned scheduling. Routine diagnostic writes remain observable without automatically creating turns. Do not generalize `actionable`'s kind/GC checks into a new events allowlist.
- Existing blacklist evidence: `dispatch/__init__.py:3556–3568` checks configured `roles_without_authority` through `held_role`, while ordinary peer delivery follows another path. This supports keeping explicit restrictions distinct from orchestration ownership.
- Tests read: `test_dispatch.py:3132–3149` checks cancellation reaches the fake adapter and records cancelled rather than done. `:4842–4871` checks editor notice/message behavior and request cancellation. `test_orchestration_transport.py:309–334` checks completion details remain stored without prompting; `:467–559` checks a routine result burst causes no turn, but a valid question wakes the system agent. Adapt these as boundary behavior examples, not as a requirement for the rebuild's current kind list.

### R4-08: Recognize existing external Node.js adapters without claiming the required service channel exists

- Classification: **Adapt** existing async subprocess mechanics; **Requires a specific decision or additional evidence** for Python–Node service and ACP placement.
- Trigger: deciding what exists already and which language should own ACP.
- Observed: `dispatch/__init__.py:259–266` configures pinned `npx` Claude/Codex ACP adapters and a Node minimum. `dispatch/registry.py:129–140,201–254` selects distributions, validates version pins, verifies supplied binary digests, and produces `npx`/`uvx`/binary argument vectors. `runner.py:4173–4184` uses the resulting subprocess with the Python ACP client. There is an asynchronous Python-to-external-Node-adapter path when an npm adapter runs.
- Separate evidence: current repository `scripts/package.json:2–11` describes build scripts with esbuild/ext-apps dependencies. `scripts/build_map_view.mjs` is a build entry, not a persistent Node service. The `src/metaform/modules/node/README.md:3–16,28–30` describes hosted Metaform/broker services and SQLite authorization state, not a JavaScript channel.
- Bounded search: inspected tracked/current-source manifest/runtime paths with `rg --files` for package manifests and JS/TS, plus dispatch `npx`/Node/start searches. No first-party Node service/session owner was established by that inspection. This does not prove an untracked/archive service cannot exist. Recovered September artifacts belong to reviewer 5's independent scope.
- Requirement: E mandates an asynchronous Python–Node channel and leaves ACP placement open. A build process, module name or npm launcher is insufficient service-channel proof.
- Smallest next step: specify the service channel and ownership contract below, compare options using the actual boundaries above, and validate both language ends before selecting placement. No engine selection or new implementation is authorized by this review.

## General event adapter proposal

This section is a reviewer proposal implementing the already decided amendment D, not an implemented feature.

1. Producers emit one semantic event envelope: stable event ID, kind/schema revision, source identity/epoch/sequence, origin reference, causation/reply identity, target(s), observed clock/time, source/content revision and typed payload or payload reference. Persistence adds journal identity/sequence. Optional observation references belong to spatial payloads rather than becoming mandatory for every message/event.
2. Publish meaningful event records once through the LadybugDB runtime service. Keep transient live observations and diagnostics separate from delivery intent. Record delivery identity per destination/context without asserting comprehension.
3. Obtain actual harness protocol/version/capability evidence. Prefer supported draft MCP Events mode. If unavailable, choose chassis-local event/message delivery with the same event identity, origin and meaning. A future harness adds an adapter/profile, not producer changes.
4. Keep discovery (`events/list` and schemas in the selected draft profile), subscription/transport, context preparation and model turn scheduling as separate contracts. Request filters choose intended destinations. They are not a new event-type permission allowlist.
5. Busy agents retain pending useful work until a supported turn/steering boundary. Own-navigation results return on that operation. Routine ticket/progress persistence causes no stream of model updates. Purposeful direct messages, assignments and event-based turns remain supported.
6. Reconnect uses journal/cursor identity and duplicate IDs. Persist pending/submitted/completed/unknown delivery states. A crash after ACP submission is unknown until evidence resolves it. A local transport acknowledgment proves only the boundary that acknowledged it.

ECS changes required: `contracts/event.schema.json:5–25` currently requires observation fields even for a supposedly general event. Amend that shape for nonspatial events. `03-technical-specification.md:413,623–637` and the `mcp-subscription-*`/notification fixtures describe resource-invalidation delivery; retain the journal semantics while superseding that sole transport prescription.

## Harness compatibility matrix

| Environment/profile | Evidence available | Required transport behavior | Limit |
| --- | --- | --- | --- |
| Codex | Owner amendment D identifies current support. Current repository config includes Codex ACP adapter at `dispatch/__init__.py:261`. | Prefer draft MCP Events only after observing the actual supported profile/version. Use chassis-local fallback when that connection lacks it. | This review did not open a Codex session, inspect a successful events handshake or test model injection. Owner support is a requirement/source fact, not a new interoperability result. |
| Claude / other ACP adapters | `proxy.py:48–120` and `serve.py:641–666` inspect ACP features; `serve.notice` at `:381–389` chooses a notice or editor message. | Negotiate independently. Chassis-local event/message if draft Events absent. | An editor-visible notice/message is not automatically an agent-model turn. Need the actual local message-to-model adapter. |
| Existing July MCP profile | `server.py:2745–2757,3219–3230` supports SDK subscription/list/resource notifications. | Preserve invalidation as needed and add the selected draft Events adapter. | Existing resource subscription is not proof of domain Events support. |
| Legacy MCP profile | `server.py:2795–2802,2827–2832` chooses connection notifications by protocol version. | Keep compatibility where useful, with general local fallback. | No inference that a host turns resource notices into useful context. |
| ChatGPT Work webhook integration | Official OpenAI documentation accessed 2026-10-29 documents draft event webhook delivery. | Only adopt if this harness is actually in scope and capabilities match. | Not evidence for the owner's Codex installation or this repository. |

External protocol check: the [MCP Events draft design sketch](https://github.com/modelcontextprotocol/experimental-ext-triggers-events/blob/main/docs/design-sketch-proposal.md) calls itself draft and defines event discovery plus distinct delivery modes. The [official OpenAI MCP Events page](https://developers.openai.com/plugins/build/mcp-events) documents webhook support and excludes polling/stream delivery for that integration. These reinforce version/mode selection, not a universal support assumption. No web content was executed. No poll mode is proposed for Metaform.

## Required asynchronous Python–Node channel: contract outline

All points below are proposed acceptance/specification work, not new code. They preserve amendment E without choosing ACP ownership.

| Concern | Required boundary |
| --- | --- |
| Handshake | Channel version, implementation version/build digest, supported operations, ACP/MCP profiles, maximum frame sizes, stream/backpressure behavior and reconnect capability. Unsupported profiles fail explicitly. |
| Identity | Separate logical agent, context epoch, harness session, process incarnation, channel request, stream and semantic event IDs. Keep Address and Join references distinct from transport IDs. |
| Session ownership | Exactly one process owns each live ACP connection/session lifecycle. The other uses explicit async operations and observes state. Durable logical identity/history belongs in the selected LadybugDB runtime service. No duplicated SQLite session store. |
| Turns and streaming | Multiplex correlated requests with per-session turn ordering. Carry text/tool/state updates and complete/failure settlement distinctly. In ACP v2, prompt accepted/message ID differs from completed turn. Preserve native IDs/upserts rather than appending duplicate history. |
| Cancellation | Request ID plus session/turn identity and incarnation. Correlate cancellation to its hop. Distinguish requested, accepted and settled. A late cancel cannot affect the next queued turn. |
| Events | One canonical envelope, retained origin/causation/source revision, target and event ID. Route through draft-MCP/local adapter after capability selection. Diagnostic streaming cannot automatically create model turns. |
| Flow control | Bounded queues, defined overflow/refusal and payload limits. Large observation data can use revisioned references or a specified binary representation. Blocking IO stays off the main loop. Current unbounded `_Output.queue`/`_lines` queues (`serve.py:224,267`) are not a proposed service guarantee. |
| Failure and reconnect | One connection-close callback settles transport futures. Readiness barrier before accepting new work. New incarnation invalidates stale control requests. Resume only if actual adapter supports it. Reconcile uncertain submitted work against journal/session evidence. |
| Persistence | Commit domain mutation/journal metadata under the new writer contract, retain delivery ledger and cursor in RuntimeRecord, and expose source revisions to both languages. File caches/process records must be explicitly classified as ephemeral or durable. |
| Shutdown | Stop accepting work, settle/cancel active requests according to protocol, flush durable records, close providers/ACP session, terminate owned subprocesses and release transient registrations. Preserve historical identity. |
| Security boundary | Local peer authentication and token handling use actual deployment boundary, explicit configured blacklist and existing authorization. No inferred supervisor role or mandatory reviewer step. |
| Observable proof | Fixture tests exercise both actual Python and actual Node endpoints, fragmented/oversized frames, multi-session interleaving, cancellation races, crash after submit, reconnect/duplicate events and slow readers. Model responses are unnecessary for deterministic channel proof. |

## ACP placement comparison, decision remains open

| Ownership | ACP in Python | ACP in Node |
| --- | --- | --- |
| Live sessions | Existing runner/serve already own subprocesses, locks, per-session maps and cleanup in Python. Retain these through a storage redesign. | Node becomes sole ACP lifecycle/session owner; Python receives native-to-semantic lifecycle observations over the new channel. |
| Streaming | Reuse Python correlated futures, update normalization and transport observers. Node handles another required runtime role. | Node owns stream parsing, native message/tool upserts and flow control. Python owns durable records/context selection and receives bounded updates. |
| Cancellation | Keep `Session.interrupt` and per-hop mapping. Channel cancellation must reach Python owner and settle back to Node. | Move active-turn cancellation state and process tree ownership with ACP. Python requests cancellation, never directly kills an independently owned Node child. |
| State | Current in-memory and persistent state separation needs extraction regardless. LadybugDB service remains canonical for durable records. | Avoid shadow session state in both processes. Node state is live transport/ACP state; durable state changes use the same service contract. |
| Failures/recovery | Python restart loses live ACP connection; Node needs explicit failure notification and recovery negotiation. Existing retry/resume mechanics are evidence, not automatic correctness. | Node restart loses its ACP connection; Python tracks submitted/unknown outcome and reconciles. Moving SDK calls alone is insufficient. |
| Cost/benefit | Less movement of already implemented ACP lifecycle and tests. Requires proof that Python can honor chosen current protocol profiles. | May align with Node-side native integrations if those are actually selected. Requires porting lifecycle, cancellation, stream semantics and recovery evidence. SDK preference alone does not establish benefit. |
| Evidence next | Pin supported profiles and exercise existing Python ACP boundary against no-model peer, then the required Node channel. | Implement no rebuild now. First compare an explicit ownership design and deterministic two-process contract demonstration in a later authorized phase. |

No placement is selected here. The narrow decision is which process owns the live ACP connection and associated lifecycle state, with the other remaining an asynchronous participant. Chassis location and the `node` module name do not answer it. The [ACP TypeScript connection documentation](https://agentclientprotocol.github.io/typescript-sdk/classes/ClientSideConnection.html) confirms a Node-side lifecycle API exists; that is library availability evidence, not a Metaform implementation result.

## Sensor amendment F at this boundary

The old forward profile remains an optional conventional profile, not virtual-surround geometry. ECS `03-technical-specification.md:519,570,591–595` describes forward positive-z axial depth and a reference reflex controller. Amend it without imposing autonomous NPC behavior:

- Physical: camera/depth overlay, 3500 mm and stated 60-degree FOV.
- Virtual: eight spherical wedges around 360 degrees with top-to-bottom distribution. Events identify the triggering 45-degree zone and up/down angle. Queries remain available independently of events.
- Virtual values preserve unsigned 16-bit millimeters through 65535 mm. Do not encode through signed int16 or a physical 3500 mm cap.
- Virtual can also expose the conventional 3500 mm/60-degree profile and its sensor-value array.
- Agent-authored code may derive events and actions. Head turns/image reads and stealth NPCs are consumers, not mandatory reactions or MCP detection policy.
- Geometry, distance semantics, source/calibration/frame and profile identity travel with observations. Final polar/zone boundary conventions and event payload schemas need specification refinement using these settled outcomes.

## Evidence and execution ledger

Read tests, not executed: the named test bodies and assertions above. Read isolation at `conftest.py:11–16,25–43`: temporary home, fake agent commands and Full Auto disabled by default. Read `pyproject.toml` test paths/addopts: browser tests excluded normally. No pytest run was necessary to resolve the source-boundary conclusions. No paid agents, model sessions, install, deployment, migrations or archived scripts were run.

Commands executed: `cat`, `head`, `sed`, `nl`, `wc`, `rg`/`rg --files` against the pinned snapshot and installed skill files; one malformed shell-quoting read command failed before doing work and was corrected. Read searches covered source/test event method names, ACP version/cancellation/provider consumers, manifests/JS/TS entry points and Node/npx launchers. Web search/open access used only primary MCP/OpenAI/ACP sources for changing protocol claims. The report itself is the only repository file written by this reviewer.

Sources read: root AGENTS/CLAUDE/README, next_spec README; archived SPEC, decisions and lifecycle/delivery; ECS paper/technical sections and event/spatial/notification contracts relevant to this scope. Some larger read outputs were truncated by tool limits, so this report cites inspected portions and does not claim an exhaustive all-lines audit of every large document or runner branch. Parent graph generation `2026-10-29T06:06:33Z` indexed the local checkout, so structural graph positives were navigation only; pinned direct source governs citations.

Proposed acceptance checks, not executed: real Python–Node endpoint contract tests; LadybugDB committed-change/journal coupling; draft-Events capability handshake for actual Codex profile; fallback parity with preserved event identity/origin; no-turn/no-read unrelated-event bursts; purposeful peer delivery without fixed type allowlist; reconnect and post-submission uncertainty; all sensor-profile unsigned-range/geometry boundaries. Legacy fixture success cannot substitute for these rebuild checks.
