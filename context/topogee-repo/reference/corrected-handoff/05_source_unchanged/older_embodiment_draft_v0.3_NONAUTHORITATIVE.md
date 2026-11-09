# Metaform — Three-Paradigm Embodiment and Perception Interface

**Engineering specification — review draft v0.3**  
**Date:** 2026-10-28  
**Status:** Proposed, not implemented. Intended as an extension/reconciliation of the October 27 ECS review and the October 22 Continuum World architecture; not a replacement for the functional typology or the authored Canonical Intake procedure.

## 0. Design intent and authority

Metaform shall allow an agent to encounter, discover, and use relevant context and capabilities while situated in **functional**, **virtual**, or **physical** environments. The agent-facing interaction semantics shall be consistent across those environments; their internal models, limitations, and transports remain distinct. The design shall reduce indiscriminate prompt loading through **progressive discovery** and **event-driven context delivery**.

This document distinguishes:
- **Agreed direction:** points established during architectural discussion.
- **Proposed contract:** specific interface shapes and implementation mechanics offered for review.
- **Unresolved:** decisions requiring validation or owner refinement. These are not silently treated as requirements.

**Agreed direction:** Retain the existing **Python chassis and working module lifecycle** in the initial implementation; strip the legacy command-centric interfaces and incidental feature modules; place the new MCP agent-facing boundary in a **Node/TypeScript module or process**; retain Python as a dynamically authored, noncompiled extension language; consider selective migration to Rust later. Chassis ownership of data, DAO, transaction lifecycle, module registration, and internal event handling is preserved. No individual sensor or physical robot needs an MCP server. The extension system remains open to capabilities the platform designers did not anticipate.

A standard interface does **not** mean a fixed list of sensor types, engines, behaviors, or skills. It means predictable discovery, invocation, context acquisition, and event semantics for whatever a module provides.

## 1. Conceptual model

### 1.1 The three paradigms

| Paradigm | Situated position | Perception/encounter basis | Example |
| --- | --- | --- | --- |
| Functional | Functional Address, receiving-element-owned Join, current work scope | Address ancestry, operative purpose, encounter function, contextual relationships, attached information | Agent encounters a navigation component and discovers its relevant specification or skill. |
| Virtual | World, entity, simulated spatial region, pose | Raycast, overlap, collision, proximity, world events, custom capabilities | Agent approaches a simulated obstacle and receives a proximity event. |
| Physical | Device/robot, sensor frame, real location or body state | ToF, camera, encoders, IMU, contact, device-originated events, custom capabilities | Agent remotely inhabits Microduck and perceives a nearby object. |

An **encounter** is a report that a particular provider has made a particular object, relationship, contextual resource, or executable capability relevant to the agent's current situation. It is **not** a claim that all three paradigms share Euclidean geometry.

Functional proximity is semantic/relational; spatial proximity is geometric. Sensor readings and physical geometry are not stored as functional graph structure merely because their events are discoverable through the same interface.

### 1.2 Shared agent-facing vocabulary (proposed)

- **Position:** Where the agent is situated in a particular paradigm, expressed using that paradigm's reference frame.
- **Encounter:** A discovered relevant entity, resource, event, or capability; contains a compact descriptor and stable reference.
- **Capability:** A typed, discoverable operation or observation with a provider-defined schema and declared operating constraints.
- **Resource:** Versioned content that may be inspected and selectively acquired, including skills, specifications, knowledge, or simulation artifacts.
- **Observation:** A point-in-time or streamed measurement attributable to a provider, timestamp, reference frame, and quality characteristics when applicable.
- **Event:** A change or encounter notification capable of waking an agent or supplying a new relevant descriptor.
- **Action:** An invocation of a discovered capability; the provider determines how it is executed.

The vocabulary is extensible: a module may define new capability kinds, schemas, and data types. A new kind does not require changing the chassis or adding a bespoke global tool name.

## 2. Component boundaries

### 2.1 Python chassis — initial owner of durable semantics

The chassis owns:
1. Data/DAO contract, transactions, graph persistence, module-contributed data declarations and operations.
2. Module discovery, compatibility, enablement, lifecycle, and registration withdrawal.
3. Contextual resolution of functional Addresses, Joins and attached knowledge.
4. Internal event distribution and collection of durable or transient change notifications as specified by the producing modules.
5. Session-related context delivery receipts and work continuity where implemented by modules using the shared contract.

Initial target: **LadybugDB-backed functional graph**; remove the NetworkX whole-graph projection as an implementation dependency. Database internals are not MCP, intake, or agent prompt vocabulary.

### 2.2 Node/TypeScript MCP module — agent-facing protocol

Node owns the MCP protocol boundary: tool schemas, MCP resources and skills exposure, session-facing discovery and presentation, event-to-agent delivery as supported by the client/harness, and correlation of requests and results. It does **not** independently own functional graph data or invent its own conflicting module registry.

Node invokes the chassis through a **versioned internal IPC interface**. The IPC serialization and transport are implementation choices; the protocol semantics must be specified independently of Python or Rust. Node should be replaceable without data migration.

### 2.3 Environment adapters — user-extensible modules

Adapters translate provider-specific sensing, actuation, physics, or graph encounters to and from the shared contract. Examples: functional namespace adapter; Bevy/WASM reference world; Continuum World/Three.js/Rapier; Godot or Unreal adapters; Microduck Wi-Fi adapter. No one engine is mandatory.

A physical robot uses its **native lightweight control/telemetry transport** over Wi-Fi or another device link. Camera/video and high-rate sensor frames may use a specialized stream outside MCP. MCP exposes discovery, resource references, current observations, actions, and event subscriptions; it is **not** required to carry every video frame, joint update, or reflex-loop message.

### 2.4 Fast and slow loops

Fast reflex, balance, motor control and frame-rate world simulation remain local to the embodiment provider. Slower, deliberative agent reasoning and prompting occur upon request or selected events. Transport latency and model inference are not in a robot's balance-control loop.

## 3. Stable MCP contract (proposed names and shapes)

This section specifies a small **generic agent-facing surface** rather than one globally visible MCP tool for every module command. Names shown are proposed and can be renamed together without changing the semantics.

| MCP operation | Input | Return | Semantics |
| --- | --- | --- | --- |
| `metaform_orient` | `scope?`, `position?` | Current situated view; compact encounter descriptors | Establish current orientation without delivering full resource bodies. |
| `metaform_discover` | `position?`, `query?`, `cursor?`, `limit?` | Encounter descriptors and next cursor | Progressive discovery in relevant functional or spatial scope. |
| `metaform_inspect` | `ref` | Detailed metadata and schema, not necessarily resource body | Find out what a discovered item does and how to use it. |
| `metaform_acquire` | `ref`, `version?` | Requested resource content or stream handle; receipt metadata | Deliberately load a skill, specification, or data resource. |
| `metaform_invoke` | `capability_ref`, `input`, `request_id?` | Typed result or async operation reference | Perform a discovered operation according to provider-declared semantics. |
| `metaform_subscribe` | `scope`, `event_filter?` | Subscription reference, current cursor | Register for encounter and environment events. |
| `metaform_unsubscribe` | `subscription_ref` | Removed subscription reference | Stop the named subscription. |

**Intake** is a separate authored workflow exposed through the same encounter/discovery model, using a small semantic submission contract defined in Section 6; it need not be globally injected into every agent's default tool catalog.

An agent must be able to inspect an unfamiliar capability, learn its input/output schema, and invoke it without a new top-level MCP command. It must also be able to discover capability descriptions without loading their full instructions.

### 3.1 Common envelope (proposed JSON contract)

```json
{
  "contract": "metaform.encounter/1",
  "ref": "cap://world-7/proximity.observe",
  "provider": "world-7",
  "paradigm": "virtual",
  "kind": "capability",
  "title": "Observe nearby objects",
  "summary": "Returns nearby objects in the selected spatial frame.",
  "schema_ref": "schema://world-7/proximity.observe/3",
  "version": "3",
  "position_ref": "place://world-7/agent-12",
  "content_ref": null
}
```

Requirements:
- `ref` identifies a resolvable encounter, capability, resource, or environment reference. Its internal encoding does not imply a database primary key.
- `provider`, `paradigm`, `kind`, and `version` are carried in metadata; **provider-defined payloads remain extensible** and are not squeezed into one universal sensor schema.
- `summary` is concise by design; full instructions are separate and fetched intentionally.
- `schema_ref` may expose a JSON Schema or equivalent typed description; the caller is not forced to know a new provider's implementation language.
- A capability descriptor may state range, field of view, update frequency, coordinate frame, permissions, and supported modes **when those properties make sense**. No assumption that every capability has them.
- Unknown provider-specific fields are preserved when the enclosing contract supports them; they are not evidence of an invalid new capability.

### 3.2 Examples

**Functional encounter:** `functional://code.navigation.obstacle_avoidance` exposes `purpose`, `encounter_function`, links to a specification and a skill reference. Discovering the skill is not equivalent to loading its instructions.

**Virtual encounter:** `place://sim/room-2` exposes a `depth.observe` capability declaring `360°` horizontal coverage, a world-defined range, and a virtual reference frame.

**Physical encounter:** `device://microduck-1` exposes `depth.observe` with the hardware's fixed 8×8 grid, calibrated field of view, and actual reported range. The agent can use one capability name across providers while reading each provider's declared limits.

The standardized **8×8 ToF representation** from the existing ECS review is an interoperability profile, **not a restriction on all sensors**. Virtual sensors may offer different geometries. A 64-zone profile includes an ordered 64-element depth array, units, invalid/missing-zone representation, time, calibration and coordinate-frame metadata, source identity, and quality information. Fusion or projection onto camera pixels is performed by an adapter using calibration, not assumed to be exact because the data are 8×8.

## 4. Progressive perception-to-context delivery

**Agreed objective:** An agent receives only a minimal orientation and compact descriptors, then acquires context according to its encounter and work. Agents do not inherit the entire module catalog or large working knowledge dump at every prompt.

**Proposed sequence:**
1. **Orient:** Agent receives identity, current assignment and functional/spatial position; minimum relevant descriptors, not full bodies.
2. **Encounter/discover:** The current position or an event yields references to resources and capabilities relevant to the agent's situation.
3. **Inspect:** Agent can examine purpose, provenance, schema, limits and resource version prior to acquisition.
4. **Acquire:** Agent explicitly retrieves a selected skill or contextual resource. Its exact delivered version is accounted for.
5. **Act/observe:** Agent invokes a capability and receives typed results or selected notifications.
6. **Continue:** On context exhaustion/handoff, persist identity, assignment, references, provenance and outcome records; rebuild only relevant context as needed rather than copying an entire preceding transcript.

### 4.1 Optional compact functional overview (clarified direction)

The **pure functional map** is a compact structural projection (Addresses, elements, receiver-owned purpose/Join relationships, and the functional descriptions necessary to understand those relationships), excluding supplementary knowledge layers and their bodies. It is **available on demand**, not required in every agent's initial context. When its measured size is modest, an agent may retrieve the whole structural map to establish global orientation without significant context cost; when it is large, the agent can instead use scoped views. No universal token-size guarantee is assumed.

The **one read operation** has **three explicit modes**. It is never compulsory to fetch the entire map first:

| `functional.view` mode | Focus Address required? | Result | Knowledge layers |
| --- | --- | --- | --- |
| `local_functional` | Yes | The focused element's functional structure, including all **direct** receiver-side and provider-side connections, their purposes and encounter functions, and the connected elements' identifying structural information. | **None.** |
| `global_functional` | No | The complete compact functional namespace: elements and receiver-owned purpose/Join relationships, without ancillary knowledge. | **None.** |
| `local_knowledge` | Yes | The same local structural relationships as `local_functional` **plus knowledge attached to the focused element itself**. | **Focused element only.** Connected providers' and receivers' knowledge bodies are not included. |

**During intake**, the agent normally uses `local_functional` and `global_functional` to review the shape it has recorded. **During ordinary operation**, `local_knowledge` supplies situated working context. This is a usage distinction, not a new tool or an invented restriction on which modes the interface permits.

The agent chooses when to request any mode. The complete structural map is deliberately **on demand**, not front-loaded; its cost is measured rather than presumed to fit every context window.

**Delivery invariant:** Discovery alone must not count as content delivered. A resource counts as delivered only when its actual body reaches the agent response/context boundary. Already acquired skills may remain available across navigation; their availability need not mean their entire bodies are re-sent on every turn. Treat changing versions and handoffs explicitly.

**Prompting:** The connection/bootstrap instructions are small and tell the agent how to orient, inspect and acquire. Provider-authored instructions remain resources/skills, not silently concatenated to the global system prompt. Any prompt that refers to a provider resource uses its resolvable reference/version; the complete text is acquired only when needed.

## 5. Events and embodiment timing

**Event contract (proposed):**

```json
{
  "contract": "metaform.event/1",
  "event_ref": "evt://sim/4815",
  "source_ref": "place://sim/room-2/trigger-4",
  "paradigm": "virtual",
  "type": "proximity.enter",
  "occurred_at": "2026-10-28T20:00:00Z",
  "position_ref": "place://sim/room-2",
  "subject_ref": "entity://sim/agent-12",
  "body": {"object_ref": "entity://sim/door-1"}
}
```

- Providers publish events in their own cadence; the chassis forwards relevant notifications, and an adapter can aggregate or debounce high-frequency telemetry before publishing a reasoning-level encounter.
- Subscriptions identify the scope of interest. Provider-local reflexes continue even when no LLM turn occurs.
- A received event may result in a new prompt/ACP session continuation **when that behavior is supplied by the harness**; MCP event support alone must not be described as automatically waking every LLM client.
- Durable event journals (where needed) are distinct from live sensor measurements. A functional `MapSnapshot` is a versioned view of **functional graph state**, not a timed 3D-world snapshot. World simulation checkpoints and network snapshots have their own separate semantics.
- Delivery order, replay policy, stale observations and high-rate stream handling must be specified per adapter or event class; no fabricated global frame-rate guarantee.

## 6. Intake: semantic forms, not database manipulation

### 6.1 Core principle

**An intake agent completes a semantic form about an artifact or function. The chassis translates that form into the data model through its DAO.** The agent is not asked to author Cypher, SQL, database IDs, table mutations, graph operation logs, or backend-specific query syntax.

The form's **meaning** belongs to the functional typology and authored intake procedure. The storage representation belongs to the chassis. Changes to LadybugDB layout or to a later Rust implementation must not require rewriting the intake agent's task vocabulary.

This is a stronger boundary than the current implementation's otherwise useful `intake.element` / `intake.purpose` APIs: those already avoid internal IDs and record one object at a time, but the submitted shape (`namespace_address`, `name_length`, receiver/provider arrays and Join fields) remains relatively close to the persisted graph shape. Preserve what works—incremental recording, readback, correction, resume—and separate the form schema from the persistence schema.

### 6.2 Intake workflow contract

**Agreed:** A first analysis follows the owner's Canonical Intake procedure, not a replacement invented by the interface. Preserve the owner-defined concepts: receiving element, operative purpose, providing element, encounter function, functional Address, and the roles defined by the typology.

**Proposed narrow agent-facing interface:** Two generic operations, selected through the encounter/capability surface, replace a large intake-specific command inventory. Lifecycle and bookkeeping are handled by the intake workflow/module, not imposed as extra agent commands.

| Operation | Behavior |
| --- | --- |
| `functional.apply` | Apply or amend a **block** of semantic elements and receiver-owned purpose relationships. The agent submits meaning-oriented form fields; the chassis translates the block to DAO operations and returns semantic receipts, revisions, and notices. Small repeated blocks and later refinement remain supported. |
| `functional.view` | One read operation with `mode="local_functional"`, `mode="global_functional"`, or `mode="local_knowledge"` as defined above. Local modes take a focus Address; global mode returns the structural map. No neighboring knowledge is included in any mode. |

These are proposed operation names and input semantics, **not** database queries or CLI verbs. Begin/resume, procedure acquisition, completion, and review bookkeeping remain workflow behaviors without requiring their own global command surfaces. An agent uses the **same `functional.view` during intake and ordinary operation**; the **explicit read mode** determines the knowledge boundary, not a separate tool or an implicit intake-versus-runtime switch.

**Proposed input envelope (precise mode semantics, versioned example):**

```json
{
  "mode": "local_knowledge",
  "address": "code.navigation.controller"
}
```

For `local_functional` and `local_knowledge`, `address` is required. For `global_functional`, no focus Address is needed. Each response identifies its selected mode, current graph revision, and the returned elements and directed purpose relationships. In `local_knowledge`, attached knowledge is scoped to the requested `address` and is not recursively fetched from linked elements. These are contract properties, not hardcoded capability categories.

**Proposed Pro review pass (not yet performed):** Examine the authored Canonical Intake's recursive Survey/Trace/Closure/Anneal/Proof behavior. Determine which repeated reasoning can be collected into meaningful blocks and applied in one operation without losing correctness or the option to refine. Compare total calls, context used, elapsed intake time, interrupted-run recovery, and final functional accuracy against the existing recursive process. Do not replace the owner's method without reviewing its exact procedure.

### 6.3 Form examples — semantic fields (proposed)

**Element form**

```json
{
  "form": "functional.element/1",
  "name": "Obstacle avoidance",
  "functional_address": "code.navigation.obstacle_avoidance",
  "role": "SE",
  "encounter_function": "Uses nearby depth observations to select collision-avoiding motion.",
  "evidence": [{"kind": "file", "value": "src/navigation/avoid.py"}],
  "notes": "Input comes from the current depth provider."
}
```

**Receiving-purpose form**

```json
{
  "form": "functional.purpose/1",
  "receiver": "code.navigation.controller",
  "operative_purpose": "Move without colliding with nearby obstacles.",
  "providers": ["code.navigation.obstacle_avoidance", "code.sensors.depth"],
  "provider_encounter_function": "Supplies avoidance decisions from measured depth.",
  "information_flow": "receives",
  "evidence": [{"kind": "file", "value": "src/navigation/controller.py"}]
}
```

*Editorial note:* The names and optional fields above are proposals to be reconciled with the Canonical Intake's exact vocabulary. In particular, an `encounter_function` on an element may be redundant or incorrectly situated if the owner's shape says EF belongs to a **receiving-element-owned Join**. In that case the form should not invent a new persisted element field. The correct rule is: a form can gather explanation useful for reasoning, but only the appropriate receiver-owned relationship maps to EF in the functional graph. The semantic form and persistence projection are intentionally distinct.

**Formal acceptance:** The agent submits **what it knows**, not an `INSERT`, `MERGE`, `CREATE`, internal node ID, transaction handle, or a textual database query. The chassis resolves subject/provider references and maps the form into one or more DAO operations, returning semantic receipt and any notices.

### 6.4 Chassis-owned form translation (proposed)

```
Agent reasoning / authored intake procedure
    -> discovered intake semantic form
    -> MCP semantic block apply
    -> Node protocol translation (no business rules)
    -> chassis intake module
    -> semantic reference resolution
    -> chassis-owned DAO transaction
    -> LadybugDB graph / associated durable records
    -> semantic receipt + notices + updated encounter references
```

A submitted form does not need to mirror database nodes/edges one-to-one. One form may create/update multiple internal records; a future internal schema may change without altering that form's meaning.

- **Incremental blocks:** Commit bounded groups of semantic contributions as the agent reasons them; do not require either one call per object or one giant whole-project submission. Preserve partial progress and subsequent refinement.
- **Readback:** Return exactly the meaningful fields and relationships the agent expects to review, not a raw database row or `Cypher` result.
- **Refinement:** Preserve an earlier contribution's provenance, content and revisions. Return what changed in domain terms.
- **Incomplete content:** Preserve a partial but meaningful submission with field-level notices where possible, consistent with the existing principle that an intake must not arbitrarily block information that can be retained. Distinguish malformed transport envelopes from imperfect semantic content.
- **References:** Functional Addresses can remain first-class *domain identities* for reasoning/navigation. They are not internal LadybugDB node IDs or instructions about database layout. Resolve ambiguous references explicitly in the receipt, not by guessing.
- **Version:** Keep the procedure revision, form schema version, submitted evidence and author/session provenance with each contribution.
- **Separation:** Intake never reads/writes the database directly. Its module calls the public DAO and the chassis owns transaction behavior.

### 6.5 Form readback and encounter integration

A new functional element/purpose becomes available for navigation after the corresponding published functional graph state changes. At a functional Address, an agent can encounter relevant form-derived resources and skills. A skill encounter delivers its descriptor; acquisition delivers instructions. The same event interface can notify the agent of a newly available skill.

**Do not confuse** the agent's semantic intake submission with a world simulation sensor reading or a spatial state checkpoint. All may lead to encounters, but they are different kinds of authored or observed information.

## 7. Module contract — retain useful lifecycle, replace command coupling

**Current source-derived behavior to retain:** Module discovery from system, user, installed entry point and project; declaration parsing prior to executing module code; enable/disable without editing chassis code; `start`/`stop`; subscriptions; module-owned tasks cancelled on unload; `Provides(kind, value)` cross-module discovery; `Tables` and `Data` declarations serviced by the chassis DAO. See the repository references below.

**Proposed additions/changes:**
- A Python module declares **capabilities, resources, encounter providers, event subscriptions, and optional intake form handlers** instead of a required inventory of CLI verbs.
- Provider-specific schemas and behavior are extendable by users at runtime, including new sensors and world mechanisms.
- Module data declarations are still executed through the public DAO; the chassis, not the module or Node, owns storage and transactions.
- MCP discovery is dynamically built from enabled providers, current functional scope, and capability descriptors. Module registration alone need not flood each agent's context.
- Enable/disable/unload withdraw a module's live capabilities/subscriptions while preserving its recorded data and provenance under the chosen data-retention policy.
- A later Rust partial core can implement the same chassis-side service contract without requiring the MCP layer to know whether the implementation language changed.

**Initial internal IPC request/response (proposed):**

```json
{
  "version": 1,
  "request_id": "req-27",
  "operation": "capability.invoke",
  "caller": {"session_ref": "session://a-12"},
  "target_ref": "cap://microduck-1/depth.observe",
  "input": {}
}
```

The counterpart response returns `request_id`, status, structured result or error and optional event/resource references. Specific wire framing (Unix socket, named pipe, local WebSocket, etc.) remains an implementation decision. The agreement to use Python now must not be mistaken for a requirement that Node import Python code or access LadybugDB independently.

## 8. Build slices and acceptance tests

**Slice A — chassis/API:** Strip the obsolete command-shaped agent surface from a test installation while preserving module discovery, lifecycle and DAO semantics. Implement one provider with a descriptor, typed schema, invocation and unload. Show that disabling the module removes discovery without breaking stored data.

**Slice B — Node MCP boundary:** Connect one Node MCP implementation to the Python chassis. Verify that `orient`, `discover`, `inspect`, `acquire`, and `invoke` return coherent data with stable refs and provider-defined schemas. An unanticipated new Python capability appears automatically without adding a Node top-level tool.

**Slice C — semantic intake → persistent graph:** Run one authored intake fragment with two elements and one receiver-owned purpose record. Submit them together as one semantic block using `functional.apply`. Read back using `functional.view(mode="global_functional")` and `functional.view(mode="local_functional", address="…")`. Then attach distinct knowledge bodies to the focus and each adjacent provider/receiver; call `functional.view(mode="local_knowledge", address="…")` and confirm **only focus knowledge** appears, while all direct functional relationships remain visible. Confirm both structural modes disclose **zero knowledge bodies**. Verify that receipts, evidence, provenance and notices reflect the requested focus and revision; the agent never submits Cypher/SQL or internal graph IDs. Repeat the same semantic form against a changed backing schema and show identical semantic readback. Preserve block-level progress, resume and revision behavior.

**Slice D — functional encounter/skill:** Navigate to a functional Address. Receive a concise skill descriptor. Load the exact skill only on `acquire`. Verify token/byte usage and actual delivery receipts; navigation alone did not inject the full skill.

**Slice E — virtual embodiment:** Use a Bevy/WASM or other selected reference adapter to produce a depth/proximity observation and a trigger event. Verify the provider declares its geometry, schema and frame independently. Local reflex/world simulation does not wait for an LLM.

**Slice F — physical embodiment:** Use a Microduck or sensor mock over a lightweight device link. Acquire 8×8 depth observations and an action capability over the external adapter. Disconnect/reconnect and verify stale measurements are identifiable and onboard/local motion control is independent of MCP availability. No MCP server runs on the device.

**Slice G — parity and context measurement:** One agent session moves between virtual, functional and physical encounters. Compare observations and high-level capability discovery where semantics match, while verifying that distinct range/FOV and implementation constraints remain visible. Measure initial prompt size, optional whole-structure retrieval size, number of on-demand content loads, duplicate deliveries and successful context continuity against the existing command-heavy implementation. No unmeasured performance claim is accepted as a result.

**Slice H — drift prevention:** Contract tests validate event envelopes, encounter refs, versioned schemas, resource acquisition, intake semantic forms and module unload. Introduce a custom new capability not known to the platform: it must remain discoverable/invocable through the generic interface, and its module may still use the chassis DAO.

## 9. Boundaries and unresolved engineering decisions

These items remain **open**; none is a prerequisite invented by this document:

1. The final generic MCP operation names and exact session/event transport supported by target agent harnesses.
2. The internal Node ↔ Python IPC framing and whether Node is hosted as one standalone process or a module-managed child process.
3. The exact LadybugDB persistence schema, graph transaction API use, package matrix and migration from historical SQLite maps. NetworkX projection is not a target requirement.
4. The intake semantic form field list, especially avoiding duplicating `EF` outside the receiving-element-owned Join; reconcile against the owner's complete Canonical Intake text before stabilization.
5. The initial world reference adapter: Bevy/WASM (preferred candidate from discussion) versus a Continuum World integration; both are optional implementations of the same contract, and their current designs differ.
6. Stream transports and timing/error behavior for each physical device or simulator, including reconnect and calibration metadata.
7. Durable event journal retention versus ephemeral high-rate telemetry: choose by actual event semantics and measured needs.
8. Performance budgets for graph queries, event routing, IPC, intake submissions and prompt delivery, to be set after a representative reference workload.

## 10. Explicit non-goals for the first implementation

- Preserve legacy CLI commands, Twilio, or unrelated proof-of-concept modules merely because they exist.
- Require every device to run MCP, every runtime to use Bevy, or every world to use a specific ECS engine.
- Stream every camera frame or every servo command through MCP/LLM inference.
- Treat spatial meters as functional Address distance, or world state checkpoints as functional `MapSnapshot`.
- Give an intake agent database query syntax or make backend storage schema the form it has to fill.
- Assume a Rust rewrite is required now, or preemptively break working Python DAO transactions to accommodate one.

## 11. Source/reference status

This is a **proposed extension**, not a claim that the draft operations are already implemented. Grounded in the existing Metaform repository and earlier conversation:

- `ecs/Inference-Metaform-ECS-Terminology-Review.zip` (2026-10-27) — reviewed ECS/functional-graph/physical-sensor proposal and technical contracts, including functional `MapSnapshot` and 8×8 ToF interoperability.
- [`src/metaform/module.py`](https://github.com/RchGrav/metaform/blob/main/src/metaform/module.py), [`src/metaform/loader.py`](https://github.com/RchGrav/metaform/blob/main/src/metaform/loader.py), [`src/metaform/data/operations.py`](https://github.com/RchGrav/metaform/blob/main/src/metaform/data/operations.py), [`src/metaform/data/store.py`](https://github.com/RchGrav/metaform/blob/main/src/metaform/data/store.py) — current chassis, modules, DAO and transactions.
- [`docs/reference/intake-calls.md`](https://github.com/RchGrav/metaform/blob/main/docs/reference/intake-calls.md), [`src/metaform/modules/intake/__init__.py`](https://github.com/RchGrav/metaform/blob/main/src/metaform/modules/intake/__init__.py), [`specifications/04-chassis-modules.md`](https://github.com/RchGrav/metaform/blob/main/specifications/04-chassis-modules.md) (BASE-039) — existing incremental semantic intake and form fields, distinct from the proposed new intake mapping contract.
- [`docs/roundtables/7-multiplayer-extensible-world-with-chunks-and-regions-instead/architecture.md`](https://github.com/RchGrav/metaform/blob/main/docs/roundtables/7-multiplayer-extensible-world-with-chunks-and-regions-instead/architecture.md) — Oct. 22 Continuum World **design-stage** proposal; does not prove a world engine is implemented.

**Owner review focus for v0.3:** Confirm the **two-operation** `functional.apply` / `functional.view` surface and **three explicit read modes**: `local_functional`, `global_functional`, `local_knowledge`. The local knowledge view includes only the focused element's attached knowledge and its direct **structural** relationships, never neighbors' knowledge. The global view remains purely functional and on demand. Review the Canonical Intake recursion for safe block application; no Pro pass has yet been executed. Then refine the semantic form fields and minimum cross-paradigm proof. Changes to these decisions should refine the spec without pulling the old command system back into the foundation.
