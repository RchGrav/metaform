# Runtime, events and asynchronous Python–Node contract

Source: remote main `fceef55a2fb6bd9bf5f8a46310e1af84276fa9f9`. The general event/fallback design and asynchronous Python–Node requirement are owner decisions. Adapter details below are proposals. ACP placement remains open. Full source/test records are in [reviewer 4](reviewers/04-RUNTIME-EVENTS.md), with context-policy evidence in [reviewer 3](reviewers/03-CONTEXT-CONTINUITY.md).

## Existing mechanics and reuse boundaries

| Scenario/component | Observed source behavior | Classification, consequence and smallest boundary | Actual dependencies and tests read |
| --- | --- | --- | --- |
| Publish a module event | `src/metaform/events.py:23` refuses synchronous publish inside an event loop. `:50` awaits async handlers, moves sync handlers to threads and isolates failures. | Adapt bus subscription/invocation/cancellation mechanics through a target-compatible Context. Producers should remain unaware of harness transport. | Loader/context/relay imports transitively reach Store/home SQLite. `tests/test_map_changed.py:58`; dispatch `test_orchestration_transport.py:226` checks 350 unrelated changes cause zero reads/work. |
| Capture a committed change | `src/metaform/changes.py:42` uses SQLite set_authorizer, `:59` total_changes, `:83` concern accumulation, `:137` invocation isolation, `:188` emits map.changed. | Replace engine-specific capture. Adapt after-commit concern merging and domain-target metadata, supplied explicitly by target writer. | Store/TableTx/home writes → recorder → MCP/runner watchers. `test_map_changed.py:92`, `test_orchestration_transport.py:252` read. |
| Relay cross-process wakeups | `src/metaform/relay.py:25` supports map.changed only. `:36` uses token/private registration and blocking socket accept. `:71` acknowledges before handling. `:113` excludes producer PID. | Adapt local IPC lifecycle. It is ephemeral acceptance, not durable replay or handler/model completion. Add journal/cursor/delivery state at the target service boundary. | Registration uses home/files and imports SQLite-backed home. No current replay journal in this path was established. Reviewer 6 inspected `tests/test_relay.py:64`, `:118`, `:135` at actual process boundaries. |
| Invalidate a watched resource/catalog | MCP `server.py:2631`, `:2751` uses SDK subscription bus. `:2795` chooses by protocol; `:3496` filters before reads and `:3533` coalesces checks. | Adapt useful version-aware invalidation. Re-engineer general draft event delivery separately. A resource-updated hint is not a semantic event body or a model turn. | Watch._number at `:3435` constructs Store. `mcp/tests/test_mcp.py:2080`, `:2901` protects current notifications and zero unrelated reads. |
| Replace a stale MCP child without duplicating in-flight writes | `mcp/transport.py:79` checks staleness at calls, `:96` waits for ready successor/protocol era, `:151` waits for cancellation settlement. | Adapt pipe/correlation/readiness mechanics. Replace NewerStore/SQLite compatibility signal and specify uncertain committed outcome/retry. | Imports legacy data layer. `mcp/tests/test_upgrade.py:133`, `:178`, `:195` queries SQLite and uses existing wire fixtures. No target service proof. |
| Interpret advertised ACP capabilities | `dispatch/proxy.py:48` version_of/agent_capabilities/session_group/lists_sessions/takes_up/mcp_over_acp reads versioned dictionaries without storage calls. `serve.py:641` consumes them. | Reuse bounded pure helpers substantially unchanged for the profiles they actually support. Adapt caller/integration and future protocol constants. | proxy.py itself imports only standard-library modules. serve and the enclosing dispatch package import Context/Store. Integration callbacks/protocol assumptions still need adaptation, so whole integration reuse is unproven. `dispatch/tests/test_dispatch.py:5020`, `:5123` uses simulated/fake ACP. |
| Multiplex requests and cancel a turn | `proxy.py:175` remaps hop IDs, `:278` bounds provider requests, `:310` remaps cancel and `:364` fails pending requests on disconnect. `serve.py:106`, `:219`, `:391`, `:416` owns per-session locks, IO threads, futures and cleanup. `runner.py:5337` serializes cancellation. | Adapt correlation, per-session ordering, cancellation settlement and cleanup. Preserve a single live-connection owner in either language. | `serve.Record` at `:1225`, `:1300` and runner session_lines reach SQLite. `test_dispatch.py:3132`, `:4842` read. |
| Deliver intentional peer work without flooding | `dispatch/orchestration.py:477` actionable uses fixed kinds, then managed assignment/return ownership. `runner.py:4410` consults it, `:4481` stores disallowed delivery without a turn. `peering.py:595` renders bounded messages; `runner.py:4424`, `:4766` deduplicates/coalesces. | Re-engineer fixed-kind/owner policy. Adapt compact messages and duplicate/busy-turn mechanics. Preserve explicit dynamic blacklist and purposeful delivery, while routine diagnostics produce no automatic model stream. | SQL session lines, peering records and signal storage. `test_informational_delivery.py:80` enforces passive plain messages today, while transport tests `:309`, `:467` protect useful no-progress flooding. These assertions must be separated for the target. |

These are useful foundations, not grounds for reusing the full runner, event module or SQLite runtime tables unchanged. No latency/CPU benchmark was performed because no event implementation was changed.

## General event adapter

The producer emits a meaningful event once. A downstream adapter selects transport using the actual destination's capability, protocol revision and supported delivery mode. The owner identifies Codex as the current supporting harness. Other harnesses can adopt the draft event mechanism by adding/changing an adapter profile, without rewriting event-producing modules.

Proposed contract responsibilities:

1. A common envelope preserves event identity, source identity/epoch/sequence, source revision, origin, causation/reply, intended target and payload meaning. Persistence adds journal identity/sequence and time provenance. Transport identifiers remain separate from semantic event and agent/context identities.
2. Typed payloads cover purposeful messages, assignments, peer communication and sensor-derived events without requiring fabricated observation fields. ECS `contracts/event.schema.json:5` currently requires observation URI/sequence on every event. Generalize its envelope/payload boundary while retaining source/journal/outcome semantics.
3. The capability profile selects the supported draft MCP mechanism/mode/revision where available. Otherwise deliver a chassis-local event/message with the same identity/origin/payload. Current SDK `subscriptions/listen` and resources/updated remain useful invalidation paths, not proof the general draft is implemented.
4. Event discovery/schema, transport/subscription, payload retrieval, context preparation and host turn scheduling have separate observation records. A notice to an editor is not assumed to be a model-context message. A local socket ACK is not handler completion. A successful local ACP transport-send observation is not remote harness acceptance or model injection.
5. Routine ticket/progress/completion persistence remains diagnostic. Producers and deliberate delivery intent identify useful addressed work. Do not implement a fixed event allowlist, inferred supervisor hierarchy or mandatory reviewer/approval pipeline to suppress floods. Apply the configured dynamic blacklist without inventing a new permission model.
6. Busy targets retain useful pending work for a supported turn/steering boundary. Own-navigation context returns in that operation. Pending bursts can coalesce references while durable distinct events remain replayable. An entering and clearing event cannot disappear because a notification was coalesced.
7. Replay uses durable journal/cursor and duplicate identities. Track pending/submitted/completed/unknown at the actual boundary. A crash after ACP submission leaves unknown until evidence resolves it. Recovery must not blindly replay a possibly applied mutation or assert exactly-once model execution.

The reference LadybugDB RuntimeRecord journal/head transaction is a target specification, not an already tested implementation. Chassis-local fallback is general, including peer and assignment events. It is not a sensor-specific exception.

## Harness compatibility and evidence matrix

| Harness/profile | What is established | Required binding | What remains unverified |
| --- | --- | --- | --- |
| Codex | Owner amendment D identifies support. Current config includes a pinned Codex ACP adapter at `dispatch/__init__.py:261`. | Prefer the supported draft event profile after actual capability/version/mode negotiation. Use local fallback if that connection lacks it. | Deployed Codex build, successful handshake, actual event-to-harness/model boundary, projection/retention integration. No live session opened. |
| Claude and other ACP hosts | Existing ACP feature interpretation at `proxy.py:48` and `serve.py:641`; notice/editor-message choices at `serve.py:381`. | Negotiate independently and use chassis-local delivery where draft events are unsupported. Upgrade adapter when supported. | Editor visibility versus model injection, event wake/steering path and native retention. Do not assume lack or presence from harness name alone. |
| Current July-era MCP profile | Repository subscription/resource/list invalidation path at `server.py:2745`, `:3219` with real-server test sources. | Keep version-correct discovery/invalidation and add a draft event adapter when supported. | Current subscriptions do not prove draft domain-event support or model execution. |
| Legacy MCP profile | `server.py:2795`, `:2827` selects connection notifications by protocol. | Compatible notification handling plus general local fallback. | Exact deployed host behavior. Resource notices do not imply purposeful delivered context. |
| Future supporting harness | No integration asserted. | Implement the same semantic-event adapter/profile and version negotiation. | End-to-end interoperability must be demonstrated before claiming support. |

Primary protocol sources inspected by reviewer 4 on 2026-10-29: [MCP Events draft sketch](https://github.com/modelcontextprotocol/experimental-ext-triggers-events/blob/main/docs/design-sketch-proposal.md), [OpenAI MCP Events documentation](https://developers.openai.com/plugins/build/mcp-events), and [ACP TypeScript connection API](https://agentclientprotocol.github.io/typescript-sdk/classes/ClientSideConnection.html). The OpenAI webhook binding is a separate integration profile. It is not evidence for this repository or the owner's Codex version. No polling profile is proposed. Do not replace capability evidence with a hardcoded universal draft wire name.

## Existing Python–Node evidence

`dispatch/__init__.py:259` configures pinned `npx` ACP adapters and Node minimum. `dispatch/registry.py:129`, `:201` validates/pins launch distributions and binary identity. `runner.py:4173` launches async subprocess pipes and the Python ACP client. Running those npm adapters gives a real asynchronous Python-to-external-Node ACP path.

That is reusable process/channel evidence. It does not establish the required first-party Python–Node service contract, shared state ownership, reconnect/delivery guarantees or target backend. `scripts/package.json:2` and `scripts/build_map_view.mjs` are build-time JavaScript tooling. `modules/node/README.md:3`, `:28` describes hosted Metaform/broker services and SQLite authorization state. That module name proves no Node.js runtime/channel.

## Required asynchronous Python–Node channel outline

| Concern | Proposed contract and observable boundary |
| --- | --- |
| Handshake/readiness | Negotiate channel protocol/build/profile versions, operations, ACP/MCP support, frame/payload bounds and reconnect behavior. Reject unsupported profiles explicitly. Ready means required services are available, not merely process spawned. |
| Identity | Distinguish logical agent, context/epoch, native harness session, channel/process incarnation, request, stream, semantic operation/event and source revision. Preserve domain Address/Join references. |
| Sessions/lifecycle | Exactly one process owns each live ACP connection and native session lifecycle. The other requests operations asynchronously. Durable logical state/history uses the selected target service, with no shadow SQLite session repository. |
| Streaming | Multiplex correlated requests with per-session turn ordering. Represent accepted request, incremental message/tool/state update and settled completion separately. Preserve native IDs/upserts instead of duplicating transcript entries. |
| Cancellation | Include request/session/turn identity and process incarnation. Remap cancellation per hop. Distinguish requested/accepted/settled. A late cancel must not cancel the next queued turn. |
| Event routing | Carry the same semantic envelope through either transport. Apply actual destination capability/version and explicit blacklist. Routine diagnostic streams do not automatically become model turns. |
| Backpressure | Bounded queues, explicit overflow/refusal/recovery and payload limits. Define large observation/body references or binary framing. Blocking IO remains off the event loop. Current unbounded serve queues at `serve.py:224`, `:267` are not the proposed contract. |
| Persistence/state | One canonical owner for durable revisions, messages, sessions, delivery/cursors and unknown outcomes. Identify ephemeral process/socket/cache records separately. Publish source mutation/journal state under the specified target transaction. |
| Disconnect/reconnect | Settle transport futures on close, require readiness for new incarnation, reject stale control messages and reconcile pending/submitted work with session/journal evidence. Transport reconnection is separate from native session resume. |
| Failure/retry | Distinguish never submitted, submitted, completed and unknown. Retry by operation/event identity only with a specified outcome contract. Historical Sept10 service.py:164 already reports ambiguous mutating-query results rather than replaying. |
| Shutdown | Stop intake of work, settle/cancel active operations, flush durable state, close owned providers/connections, terminate owned children and release transient registrations while preserving historical agent identity. |
| Local access | Use actual local authentication/deployment boundary and configured restrictions. Preserve origin. Add no inferred reviewer or approval hierarchy. |
| Proof later | Exercise actual harmless Python and Node endpoints for fragmented/oversized frames, concurrent sessions, slow readers, cancellation races, lost completion, crash/reconnect, duplicate events and stale incarnation. No paid model is needed to verify deterministic transport. |

The contract does not silently choose pipes, sockets or a final wire format. Those choices follow placement/deployment and must be specified once. Existing subprocess/correlation mechanics are assets whichever endpoint owns ACP.

## ACP placement comparison

| Responsibility | ACP in Python | ACP in Node |
| --- | --- | --- |
| Sessions and lifecycle | Retains existing runner/serve ownership, locks, subprocess handles and cleanup after storage adaptation. Node invokes owner through channel. | Moves native connection/session/process lifecycle as one responsibility. Python observes logical lifecycle through channel. |
| Streaming | Existing Python parsing, futures, observations and normalization remain; Node receives bounded updates or serves other required runtime functions. | Node owns stream parsing, native update/message IDs and flow control; Python records durable bounded updates. |
| Cancellation | Existing interrupt and hop mapping stay in Python. Channel requests must route there and report settlement back. | Active-turn cancellation/generation/process-tree ownership moves with ACP. Python requests cancellation through the owner. |
| State | Extract Python live transport state from durable LadybugDB state. Avoid exposing current SQL session tables as channel contract. | Node live state is transport/session state. Durable state remains in selected service with one canonical owner, rather than duplicated session machines. |
| Failure and reconnect | Python owner restart invalidates the live ACP connection. Node receives failure/incarnation change and cannot assume native resume. | Node owner restart invalidates the live ACP connection. Python preserves submitted/unknown records and reconciles using real capability/history. |
| Adaptation cost/evidence | More existing lifecycle/test mechanics can remain in place. Actual selected protocol support and target persistence still need proof. | Can place ACP alongside selected Node-native integrations, if those benefits are established. Requires transferring cancellation/stream/lifecycle/recovery semantics together. SDK availability alone is insufficient. |
| Narrow decision | Choose if Python is to own the live ACP lifecycle, after channel/profile evidence. | Choose if Node is to own that same complete responsibility, after channel/profile evidence. |

Neither is selected. The chassis language, preferred SDK and hosted “node” name do not settle this ownership decision. Whichever is chosen, define one state machine and demonstrate its boundaries rather than maintaining competing live session owners.

## Sensor control profiles and event meaning

Owner amendment F supersedes universal forward axial-depth geometry in the archive. ECS technical `03-technical-specification.md:519`, `:570`, `:591` and `contracts/spatial-tof.schema.json:108` currently fix 8×8/row-major/axial-z; calibration assumes forward positive-z rays. Correct those as profile-specific contracts. No current signed-16 implementation defect is asserted merely from this source. The new unsigned range is an explicit required acceptance boundary.

| Profile | Required data/control behavior | Boundary |
| --- | --- | --- |
| Physical | Camera view with depth-grid overlay, stated 60° FOV and up to 3500 mm, source/calibration/quality provenance. | Do not present ideal raycasts as equivalent physical measurements. Hardware calibration remains deployment evidence. |
| Virtual conventional | Optional conventional 3500 mm/60° profile and readable sensor-value array. | Forward optical/axial conventions may describe this declared profile. They do not define surround geometry. |
| Virtual surround | Query-at-any-time 360° sensing, eight spherical wedges with top-to-bottom distribution, full unsigned 16-bit mm through 65535. Events expose triggering 45° zone and up/down angle. | Specify angular zero/sign, vertical convention, boundaries, frame, sampling and distance meaning explicitly. Do not require all surround rays positive-z or divide by forward z at rear/side directions. |

Agent-written code can turn observations into events and actions. Rear event → head turn → image/depth read and forward stealth-game sensing remain example consumers. MCP does not impose that reaction, autonomous detection or gameplay policy. Configured local reactions may run independently of a model, but are not a compulsory behavior for every profile.

Preserve source identity/epoch/sequence, capture/read timing distinction, incident frame/calibration identity and quality/no-return semantics. A valid 65535 mm measurement must not become an invalid sentinel or signed negative value. Proposed acceptance includes 32767/32768/65535, rear/top/bottom and 45° boundaries, explicit profile switches and on-demand reads independent of event subscriptions. None was implemented or executed by this review.
