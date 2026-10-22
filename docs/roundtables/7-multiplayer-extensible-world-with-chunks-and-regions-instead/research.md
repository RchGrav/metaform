# Multiplayer world research

Stage: Researcher. Roundtable: `a4c0c884`. Ticket: `57e5143d0ca64ddaa70d1d623b52b466`.
Date: 2026-10-22. Author: curious-agent.

Build a shared, playable 3D world. People and agents use identical operations. The scene service owns accepted state. WASM extensions propose bounded effects. Metaform retains functional intent.

This document formalizes requirements and recommends SDKs. It does not name the new project or prescribe the complete architecture. Automated preparation continues through the recorded pipeline. Implementation remains inactive.

## Grounding and scope

Original request, preserved for traceability:

> Multiplayer extensible world with chunks and regions instead of redstone and voxels it uses wasm and a wasm bus ..  agents can extend world which is based on real physics...   regions can have different properties and borders.   like a multiverse A shared, playable 3D canvas where the person and agents edit the same world through one operation format, and every meaningful object and rule keeps its purpose, constraints and decisions through Metaform (I1). Its core is an authoritative scene service (I5) over a portable, renderer-independent world format with one runtime for editor, web export and headless checks (I4). Agents act through a small typed vocabulary (I7) with spatial perception (I8), propose edits as reviewable patches against a revision (I9), and prove intent with bounded simulation checks (I14). Build it JavaScript-first: TypeScript, Three.js, Rapier WASM, Web Workers (I2, I16).

Primary records: [discussion export](/home/rich/metaform/docs/roundtables/7-multiplayer-extensible-world-with-chunks-and-regions-instead/export.json), [mechanical report](/home/rich/metaform/docs/roundtables/7-multiplayer-extensible-world-with-chunks-and-regions-instead/mechanical-report.md). These supplied records reside in the target folder, outside this assignment checkout. The export contains 28 submissions, including passes. Discussion primarily addressed gateway attribution and authority. It did not establish a complete physics or multiplayer specification.

Use two distinct identifier sets. `O-I*` refers to ideas cited within the original request. `R-I*` refers to this roundtable's 21 synthesized ideas. Their numbers overlap. They are not interchangeable.

Preserve the functional core:

`C(T) = { (r_i ∧ p_i ∧ e) }: Formula for frozen core allowing mutation, not transformation.`

People receive playable, understandable changes. Agents receive bounded perception and editing capabilities. Extensions supply behavior through explicit permissions. Metaform supplies durable functional context. Replacing a renderer or storage mechanism must preserve those outcomes.

Confirmed requirements come from the request and resolved discussion. Engineering recommendations below fill missing mechanisms. They remain explicit proposals for architecture and specification. No user-only decision blocks research.

## Findings and choices

1. **Project effect.** Add a world product with a Metaform integration boundary. The existing gateway already supplies request-local attribution. It does not supply world authorization, physics, conflict handling, or extension isolation.
2. **Design benefit.** One operation contract preserves editor-agent parity. One authoritative commit path preserves permissions, revisions, and recovery. One shared runtime prevents exported worlds from changing behavior.
3. **Existing rationale.** Metaform serves local tools and agent sessions. Its process-session fallback supports that environment. Shared worlds require authenticated principals, so copying that fallback would misattribute edits. The discussion explicitly corrected this proposal.
4. **Recommended action.** Keep the TypeScript runtime independent of rendering. Use service-owned job records. Validate effects through trusted host code. Persist intent with each accepted patch. Export durable semantic knowledge through an idempotent integration path.

Use chunks for storage, visibility, and streaming. Use regions for permissions, physical properties, and border rules. Their boundaries need not coincide. Treat separate dimensions as independent spaces with explicit transfer rules. This separates scaling concerns from world semantics.

Recommend rigid-body mechanics as the initial meaning of real physics: SI units, gravity, mass, collision, friction, restitution, forces, and joints. Fluids, fracture, relativity, and scientific accuracy beyond stated tolerances are deferred extensions. This scope supports playable interaction without claiming a universal simulator.

## Observable requirements

| ID | Behavior and reason | Acceptance evidence | Source |
|---|---|---|---|
| WR-01 | People can navigate, select, create, move, remove, inspect, and play with objects. Agents invoke the same typed operations. | Equivalent person and agent edits produce equivalent normalized patches, authorization checks, and committed state. A second client observes the result. | O-I1, O-I7 |
| WR-02 | A portable world format stores stable IDs, units, transforms, physical components, assets, chunks, regions, rule hashes, and intent references. Renderer objects stay outside it. | Save, reload, and export preserve IDs and meaning. Headless loading needs neither DOM nor Three.js. Unsupported schema versions fail explicitly. | O-I4 |
| WR-03 | Editor, exported player, and headless checker share simulation and operation semantics. | One fixture and ordered input sequence produce matching state under the same pinned runtime. Export works without an editor connection. Multiplayer export identifies its required server. | O-I4, O-I14 |
| WR-04 | One authoritative service validates and orders durable edits. Clients display accepted revisions. | Concurrent patches against one revision yield one accepted change and one explicit conflict. Disconnect and reconnect recover a checkpoint plus missing changes without duplication. | O-I5, O-I9 |
| WR-05 | Chunks stream by interest without becoming physics or permission boundaries. | Crossing a chunk edge retains object identity, collision behavior, and authority. Client unload does not delete authoritative bodies. Large objects spanning chunks remain queryable once by ID. | Original request |
| WR-06 | Regions expose explicit boundaries, permissions, gravity, material defaults, rule sets, and budgets. | Two adjacent regions produce distinguishable declared behavior. Overlaps have deterministic priority. Invalid geometry or ambiguous priorities are rejected. | Original request, R-I2 |
| WR-07 | Border policies govern edit transfers and simulated crossings. Acceptance is atomic across affected regions. | A denied crossing changes neither ownership nor destination state. Allowed crossing preserves declared pose and velocity semantics. Fast bodies cannot bypass a border between samples. | R-I3 |
| WR-08 | Physics follows declared units, timestep, material bounds, and body constraints. | Falling bodies, contact, restitution, and a joint fixture meet stated tolerances. Invalid mass, nonfinite values, and excessive forces are rejected. | Original request, O-I14 |
| WR-09 | A small typed vocabulary supports queries, proposals, checks, and commits. Unknown operations fail validation. | Malformed payloads, unknown fields, excessive batches, missing IDs, and unauthorized targets fail before mutation. Every rejection identifies its cause. | O-I7 |
| WR-10 | Agent perception includes bounded nearby objects, bounds, relationships, region rules, and revision information. | Ray, overlap, and neighborhood queries return stable IDs with truncation/cursor information. Hidden regions and unauthorized objects remain hidden. | O-I8 |
| WR-11 | Reviewable patches carry a base revision, intended result, constraints, decisions, and bounded checks. Preview is isolated. | Review shows additions, removals, changed rules, affected regions, and evidence. Rejected previews leave live state unchanged. Undo becomes a validated compensating patch. | O-I9, R-I1 |
| WR-12 | The gateway authenticates principals. A service-issued handle binds world, principal, issue, and optional run. Identity is distinct from capability. | Forged identity fields grant no access. Two runs sharing a connection remain isolated. Missing run remains absent. Unauthenticated mutation fails. | R-I2, R-I11, R-I15 |
| WR-13 | Workers return job identity plus effects. Service-owned records resolve attribution and assigned worker. | Altered worker identity is ignored. Unknown, expired, duplicate, and wrong-worker results cannot commit. A module cannot certify its own compliance. | R-I18, R-I19 |
| WR-14 | WASM imports and bus effects are versioned, typed, permission checked, and resource bounded. | Forbidden imports, excessive memory, infinite execution, oversized messages, recursive message floods, and unauthorized effects terminate or reject the job without service loss. | Original request, R-I2, R-I19 |
| WR-15 | Trusted checks bind verdicts to patch hash, base revision, starting simulation checkpoint, engine version, module hashes, region policy versions, seed, timestep, and assertions. | Changing any dependency invalidates approval. Live simulation advancing beyond the checked checkpoint cannot silently reuse a stale physical verdict. | O-I14, R-I9 |
| WR-16 | Current authority is checked atomically with commit. Authorship remains historical. | Cancellation between check and commit blocks the old run. A person can approve its saved proposal through a new authorized request after revalidation. | R-I8, R-I16, R-I17 |
| WR-17 | Durable deduplication binds world, operation ID, canonical payload hash, and outcome. Cleanup cannot erase accepted outcomes. | Retry after lost acknowledgment and service restart returns the original outcome. Reusing an ID with different content fails. Authorization still controls access to the result. | R-I21 |
| WR-18 | Accepted patches durably retain purpose, constraints, decisions, authorship, verifier, committer, extension hashes, and causation. Metaform delivery is recoverable. | Crash between commit and delivery loses no intent. Retry creates no duplicate semantic record. UI distinguishes committed state from pending Metaform synchronization. | O-I1, R-I10, R-I13 |
| WR-19 | Persistent drafts use world, principal, and issue keys. Resume is explicit. Runtime events use a dedicated principal and current subscriptions. | Agent B cannot resume agent A's draft merely by sharing an issue. Installed behavior continues without inheriting its installer's expired permissions. | R-I6, R-I7, R-I12 |
| WR-20 | Rendering and synchronization respect event boundaries and bounded queues. | Visual work uses requestAnimationFrame. Irrelevant events cause zero reads. Slow clients trigger bounded resynchronization. Hot application loops use preallocated data and stable shapes. | Project performance rules |
| WR-21 | Every meaningful object, rule, and region can expose its functional purpose and constraints. Runtime instances can share a functional type while retaining distinct identity. | Selecting an object reaches its applicable Metaform context. Changing a rule preserves its decision record. Per-frame positions never become memory observations. | O-I1, Metaform Join semantics |
| WR-22 | World packages include versioned manifests, assets, rules, intent references, and license notices. | A package loads without network access in local mode. Missing assets, mismatched hashes, unsupported ABI, and incompatible schema fail before play. | O-I4, original request |

## Runtime contract recommendations

Recommend these initial verbs: `inspect`, `query`, `propose`, `check`, `commit`, `resume`. Patch operations cover object creation/removal, transform changes, physical-property changes, region definition, border policy, and rule installation/removal. Keep the vocabulary extensible through versioned schemas. Do not expose arbitrary JavaScript evaluation or unrestricted renderer mutation.

Separate immutable author provenance from current commit authority. The service constructs full job context after authentication. Worker copies carry context for computation, never proof of identity. Result acceptance checks both the service-issued job and its assigned execution channel. An envelope ID is not a bearer permission.

Recommend all-or-nothing batches with revision preconditions. Start with explicit conflict rejection. Automatic merge requires proven independence and belongs in later refinement. A durable edit revision and simulation tick are separate values. Physical checks additionally bind their starting checkpoint. Define a final tick boundary where checked effects become accepted.

Use a versioned world document as the portable source. Use Rapier snapshots as pinned-runtime checkpoints. Use glTF/GLB for visual assets, not permissions, region rules, or the complete world format. Canonical hashing must specify ordering and numeric normalization. Reject NaN and infinity. Store integer revisions without JavaScript precision loss.

Recommend nonoverlapping axis-aligned region volumes initially. Explicit priority resolves deliberate overlaps. Border policy names allowed movement, rejected movement, and dimension transfer. Ordinary same-dimension crossings preserve pose and velocity. Transfers between dimensions declare coordinate and velocity transforms. Objects with joints transfer as an approved connected group or fail atomically. Destination readiness and permissions are preconditions.

A single Rapier world has a global gravity vector. Gravity scaling cannot express every regional vector. Regional gravity therefore requires controlled force application or distinct physics spaces. Bodies in distinct Rapier worlds do not automatically collide. Recommend shared clocks within interacting space, separate dimensions for incompatible clocks. Architecture must specify transfer behavior instead of implying seamless cross-engine contact.

Recommend fixed simulation steps of 1/60 second initially. This is a tunable engineering default, not measured capacity. Browser rendering follows requestAnimationFrame. Dedicated server simulation uses explicit step scheduling as physical time advancement, not state polling. Headless checks run a bounded number of steps. Queue and deadline events handle synchronization. Preserve project rules against timer-based rendering and repeated readiness checks.

The WASM bus should expose versioned messages, import allowlists, payload limits, bounded queues, and deterministic ordering. Default imports supply time as simulation ticks, seeded randomness, permitted queries, and proposed effects. Do not supply ambient network, filesystem, process environment, or arbitrary host functions. Validate memory declarations and module features before instantiation.

Native JavaScript WebAssembly APIs do not provide a portable instruction-fuel budget. Worker termination supplies a wall-clock deadline, not deterministic instruction accounting. Node worker resource limits exclude external buffers. Recommend a supervised process with operating-system memory limits for untrusted server modules, plus bounded WASM memory and message quotas. Browser execution remains a preview with worker deadlines. The server independently validates every accepted effect. A deterministic fuel mechanism remains an architecture choice requiring a focused proof before claiming instruction-budget enforcement.

## SDK recommendations

Versions below were read from npm registry metadata on 2026-10-22. Pin exact versions and artifact hashes when creating the implementation lockfile. Registry metadata establishes published versions, not full-stack compatibility.

| Dependency | Recommended version and environment | Relevant APIs and purpose | License and deployment |
|---|---|---|---|
| `typescript` | `7.0.2`, build tool | Strict discriminated unions and type checking. Runtime validation remains required. | Apache-2.0. Build dependency. [Metadata](https://registry.npmjs.org/typescript/7.0.2) |
| `three` | `0.186.1`, browser ES modules | `Scene`, `WebGLRenderer`, `InstancedMesh`, `BufferGeometry`, `GLTFLoader`. Presentation only. | MIT. WebGL2 baseline. Keep notices in exports. [Metadata](https://registry.npmjs.org/three/0.186.1), [renderer](https://threejs.org/docs/pages/WebGLRenderer) |
| `@dimforge/rapier3d-compat` | `0.21.0`, browser workers and Node | `init`, `World`, `RigidBodyDesc`, `ColliderDesc`, scene queries, `step`, `takeSnapshot`, `restoreSnapshot`. | Apache-2.0. Compat package simplifies WASM loading. Release WASM resources explicitly. [Metadata](https://registry.npmjs.org/@dimforge/rapier3d-compat/0.21.0), [guide](https://rapier.rs/docs/user_guides/javascript/getting_started_js/) |
| Web Workers / `node:worker_threads` | Platform APIs, no npm version | `Worker`, `MessageChannel`, `postMessage`, termination, transferable buffers. Use a small host adapter around shared runtime code. | Platform supplied. Worker threads are not an operating-system security boundary. [Node API](https://nodejs.org/api/worker_threads.html) |
| WebAssembly JS API | Platform API | `compile`, `instantiate`, `Module.imports`, `Memory`. Narrow custom ABI before adopting a broader plugin framework. | Ship content-hashed modules. Serve correct MIME and CSP. No implicit WASI capabilities. [Standard](https://www.w3.org/TR/wasm-js-api-2/) |
| `ws` | `8.22.0`, Node server | `WebSocketServer`, upgrade authentication, messages, close, bounded payloads. Browsers use native `WebSocket`. | MIT. TLS termination and authenticated upgrades required for remote deployment. [Metadata](https://registry.npmjs.org/ws/8.22.0), [project](https://github.com/websockets/ws) |
| `zod` | `4.6.7`, service and client | `safeParse`, strict objects, discriminated unions. Validate operation and manifest boundaries. | MIT. Keep validation outside per-body simulation loops. [Metadata](https://registry.npmjs.org/zod/4.6.7) |
| `@modelcontextprotocol/client` | `2.3.1`, server integration | `Client`, `StreamableHTTPClientTransport`, discovery and tool calls. Supports current MCP protocol negotiation. | Apache-2.0 per registry. Node >=20. Credentials remain server-side. [Metadata](https://registry.npmjs.org/@modelcontextprotocol/client/2.3.1), [client guide](https://ts.sdk.modelcontextprotocol.io/v2/clients/connect) |
| `vite` | `8.3.5`, browser build | ES-module builds and worker assets. Editor and player share packages. | MIT. Node requirement: `^20.19.0 || >=22.12.0`. [Metadata](https://registry.npmjs.org/vite/8.3.5), [guide](https://vite.dev/guide/) |
| `@playwright/test` | `1.64.1`, development | Multi-context browser tests, reconnects, editor-agent flows, exports. | Apache-2.0. Browser binaries are test infrastructure. [Metadata](https://registry.npmjs.org/@playwright/test/1.64.1) |

Recommend Node `24.22.1` LTS for service and tooling. The [official distribution index](https://nodejs.org/dist/index.json) identifies that release as LTS. Local experiments used installed Node `22.18.0`, so Node 24 compatibility remains an implementation check.

Use MCP v2. The older `@modelcontextprotocol/sdk` v1 line does not support protocol `2026-07-28`. Metaform currently serves that revision. Verify negotiated protocol and tool schemas against the running server. Do not assume package-name continuity across SDK generations. [Official protocol guide](https://github.com/modelcontextprotocol/typescript-sdk/blob/main/docs/protocol-versions.md)

Avoid introducing React Three Fiber, an ECS framework, a CRDT, WebTransport, or a component-model runtime without a measured need. Three.js and Rapier already cover requested rendering and rigid-body mechanics. A single ordered authority is simpler than merging concurrent physical state. Native WebSocket provides the required reliable channel. SharedArrayBuffer is optional optimization work, with cross-origin isolation requirements.

Production hosting needs a persistent authoritative service and durable storage. Static hosting alone supports exported local play, not shared authority. Keep Metaform credentials out of exported assets. Pin module and asset licenses independently from engine licenses. Preserve MIT and Apache notices in distributed bundles. This is a dependency inventory, not a legal assessment.

## Metaform fit

Inspected project contracts: `specifications/00-index.md`, `specifications/02-layers.md` LAYER-012/LAYER-013, and relevant context records in `specifications/11-context.md`. The map indexes functional knowledge. Memory remains mutable and distinct from execution history.

Inspected implementation entry points:

- `src/metaform/context.py:31`: builds one Context and copies the identity dictionary. Session selection can fall back to process context. `session` and `identity` are distinct fields.
- `src/metaform/modules/mcp/server.py:871`: `gateway_identity` copies gateway headers without changing server environment. Header extraction alone does not authenticate an external caller.
- `src/metaform/modules/mcp/server.py:879`: `gateway_session` scopes delivery by agent/run, otherwise agent/issue.
- `src/metaform/modules/mcp/tests/test_mcp.py:1908`: existing tests cover interleaved runs, request attribution, process-session fallback, and environment preservation. They were inspected, not rerun.
- `src/metaform/events.py:23` and `:50`: existing event delivery builds receiver contexts and copies payloads. Reuse this bus for Metaform integration events. Pass attribution explicitly in validated payloads where needed. Do not assume receiver contexts inherit it.
- `src/metaform/modules/paperclip/__init__.py:409`: issue selection uses explicit input, call identity, then environment. This is integration behavior, not a shared-world authorization mechanism.

Source reads confirm these files exist in this checkout. Older map references marked `MISS` are not evidence of current absence. Code graph coverage reported matching metadata for the four checked context/event paths. Source reads supplied the material evidence.

Recommend a server-side Metaform adapter using public tools. Do not write directly into Metaform SQLite tables. Map meaningful functions through receiving elements, operative purposes, and encounter functions. Attach constraints and decisions where the receiver bears their goal. Spatial instance IDs remain application data unless they represent distinct functions.

Commit the world patch and its intent/outbox record together in world storage. Deliver semantic updates through canonical Metaform operations. Durable memory holds functional facts. Work records hold verification and execution history. An integration-owned receipt keyed by world and commit supplies delivery deduplication. Existing memory creation skipping duplicate names does not establish transaction-wide exactly-once delivery. Architecture must define recovery for partial multi-call projection.

## Evidence and limits

The [Rapier determinism guide](https://rapier.rs/docs/user_guides/javascript/determinism/) supports deterministic results with the same version, initialization, object order, and inputs. Arbitrary host math and extension behavior can break those conditions. Pin engine versions, step order, seed, and configuration. Bounded checks demonstrate declared assertions over a finite horizon. They do not prove arbitrary extension correctness.

The [Rapier snapshot guide](https://rapier.rs/docs/user_guides/javascript/serialization/) documents binary snapshots. The [scene query guide](https://rapier.rs/docs/user_guides/javascript/scene_queries/) supplies geometric perception. Neither replaces the portable semantic world document.

Two focused local experiments ran:

1. Node `22.18.0`: clone `Object.freeze({agentId:'author', runId:null})`, then change clone identity. Result: original frozen `true`, clone frozen `false`, original author unchanged, clone changed. This confirms that copied immutability cannot authenticate worker results. The [HTML structured-clone standard](https://html.spec.whatwg.org/multipage/structured-data.html#structuredserializeinternal) specifies reconstruction across realms.
2. Node `22.18.0`, Rapier `0.21.0`: create a dynamic sphere at y=10, gravity -9.81, timestep 1/60. Step 60 times, snapshot, restore, then advance both worlds 60 times. Snapshot size: 2,651 bytes. Final SHA-256 snapshot hashes matched. Final y: -9.660922050476074. Both worlds were freed. This establishes one local restore/replay path, not cross-browser determinism or performance.

Rapier was installed only in a temporary research directory. No runtime dependency or implementation was added to Metaform. Registry metadata was read directly with bounded network timeouts. No multiplayer benchmark, adversarial sandbox proof, browser parity test, or complete integration test ran.

## Required implementation proofs

Architecture and planning should retain these gates:

- Two clients plus one agent edit and play in one world. All durable edits use the common operation contract.
- Same fixture runs in editor, exported player, and headless checks. Compare canonical states and pinned Rapier checkpoints.
- Exercise adjacent regions, overlaps, fast crossings, denied transfer, jointed transfer, and destination-unavailable recovery.
- Interleave run A, missing-run B, and another A check in pooled workers. Verify attribution and delivery isolation.
- Forge result identity and job IDs. Cancel after validation. Change dependencies before commit. Accept no unauthorized or stale effect.
- Crash after commit before acknowledgment. Retry after context cleanup. Recover outbox delivery after Metaform outage.
- Run infinite-loop, memory-growth, oversized-message, forbidden-import, and recursive-bus fixtures. Verify bounded termination and healthy authority.
- Profile application allocation, draw calls, frame-time median/p95/p99, simulation-step time, queue depth, and patch latency. Record hardware and fixture sizes. Performance targets require measured reference hardware before becoming acceptance thresholds.

Capacity recommendation for the first benchmark fixture: two browser clients, one agent, two regions, four streamed chunks, 100 dynamic bodies, and one extension. This fixture is a test scope, not a production capacity promise. Increase load only after correctness gates pass.

Architecture must settle storage transactions, hard sandbox enforcement, canonical schemas, border transfer details, durable receipt projection, and protocol compatibility. These are engineering decisions supported by this brief. Product decisions about public hosting, billing, marketplaces, and mass concurrency remain outside this preparation's requested core.

No existing behavior was replaced. No obsolete implementation was removed. This stage supplies research only.

curious-agent
