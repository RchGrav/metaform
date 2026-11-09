# Metaform functional core — corrected engineering specification

**Status:** candidate v0.4; prepared for owner review and additional independent specification validation. This is a design specification, **not** a claim that implementation is complete. The current JSON model and original Canonical Intake are attached separately as primary evidence.

## 1. Purpose, non-negotiable boundaries, and terms

Metaform exists to amortize inference: build reusable functional understanding independently of any particular agent's task and make it available in the appropriate context without forcing repeated discovery. The **functional map is not a database editor**, a file browser, a replay of a chat, or a record of agent progress. Work records, knowledge, one-time notices, events, and functional relationships are distinct categories.

**C-001 — User design authority.** This specification governs rebuilding. Old code, prompts, and remediation plans are read-only evidence, not product requirements. Investigators may suggest missing functionality and useful mechanisms but may not directly transplant existing code or alter definitions without owner review. The existing modular chassis has useful engineered behavior; do not assume the module architecture itself is defective.

**C-002 — Authoritative functional vocabulary.** Use the full original semantic definitions in the attached `Canonical_Intake_old_flattened_original.xml`, especially AUE, RE, PE, OP, EF, CQU, DE, SE, NE, ICE, IFD, entity/element, parametric, and namespace. In brief: an RE holds an active OP (why); a PE serves it through an encounter-specific EF (how); IFD concerns the actual satisfying substance rather than request/parameter traffic. A PE in one join can be the RE in another, with a single namespace identity. A CQU is not a generic "user" label. Do not paraphrase those primary definitions into weaker requirements.

**C-003 — Specific names.** The field `op` means **Operative Purpose**, not an ambiguously named `purpose`; the relationship is a **provider join**, not a purpose join. `ef` means **Encounter Function**. `ifd` means **Information Flow Direction**. Fields must name the concepts they contain. The provider address is the dictionary key; do not also require a synthetic provider ID in that record.

**C-004 — Acceptance priority.** Preserve functional semantics, user authority, valid dependencies and measured cost. No hidden agents, fan-out of hundreds of MCP tools, automatic informational model turns, default bulk context dumps, or gates added merely because a framework suggests them.

## 2. Functional namespace (logical, not physical storage)

**F-001 — Addressing.** The current structural baseline is the user's latest hierarchical JSON Schema. Dotted namespace addresses arise by traversing nested keys from the root (e.g. `code.client`), not through a mandatory top-level `metaform` wrapper unless separately approved. Root values may be nested namespace objects, JSON arrays (composed element layers), or scalars. Do not create artificial IDs for every node or collection entry, or assume array ordering carries semantic ordering. Names are type-level reusable functional terms, distinct from AUE-specific provider encounters.

**F-002 — Metadata and keys.** Metadata properties and structural namespace words may share spellings in different locations. An implementation must use schema/context, not string matching on a leaf name, to distinguish them. `name` holds project-specification canonical name when one exists and otherwise the established industry name; `label` is separate and is not a second namespace identity. `name_length` is an ancestry lookback count, not an opaque ID.

**F-003 — Roles.** Inside the AUE, roles DE/SE/NE describe functional elements. External CQU is a receiving party type in `downstream.cqu.*`, not a PE role. RE and PE name positions **in a provider join**, not permanent role strings on elements. Do not infer every element must always be only provider or only receiver.

**F-004 — Receiver-owned provider join.** Each receiving element may have a `providers` dictionary. Each key is a providing element's full namespace address. Each value contains **`op`, `ef`, and `ifd`** for that RE/PE encounter. The provider join identity is `(receiver_address, provider_address)`; this is not a global EF definition of a PE. The model permits PE reuse across many REs with different EFs for the encountered relationship. Multiple distinct encounters between the same ordered pair, if required, need an explicit future cardinality decision rather than a silently invented `id`.

**F-005 — Referential integrity.** JSON Schema validates local shape but cannot ensure each provider address exists or is an authorized external reference. The chassis performs cross-document/graph validation and reports nonblocking source-grounded notices where appropriate. Neither semantic correction nor deletion occurs invisibly.

**F-006 — Data categories.** Permanent functional element facts, attached knowledge, mutable state, work history, pending mailbox notices, delivery receipts, and spatial/physical observations must remain distinguishable. The current JSON Schema permits arbitrary nested values and array layers; it does not license conflating them or inventing a universal `knowledge_record` wrapper. No other schema variant in the recovery folder supersedes the latest upload.

**F-007 — ICE.** Original intake requires detecting indivisibly coupled elements *during* dependency tracing and verifying them at closure, not inferring coupling from a mere import, call, or common file. Latest uploaded schema has provider-join `ice: boolean`, but legacy intake also has multi-element ICE block identifiers. The boolean is **not** an ICE group ID; preserve the distinction and do not claim a complete block-partition contract exists until approved. Coupled work must not be split merely by file/worktree boundary.

**F-008 — Namespace quality.** Apply original typological rules: no filler taxonomy; reverse-reading dotted names should recover a recognized noun phrase; narrow functionally trunk-to-leaf; no genre, encoding, style, programming language or arbitrary parametric proliferation. Canonical project name priority and continuous auditing during refinement remain requirements; do not invent nomenclature. Preserve original constraints that a nameable detail need not deserve a new element.

## 3. Functional agent interface: exactly two baseline operations

**T-001 — Functional read operation:** `functional.view` is a *working name* for **one agent-facing operation**, not one MCP tool per graph command. It supports exactly three required modes:

| Mode | Input | Content returned | Forbidden default content |
| --- | --- | --- | --- |
| `local_functional` | Focused namespace address | Focus node identity and concise functional properties; directly connected provider joins and receiver-side reverse links; OP, EF and IFD for each join; neighbor identity stubs | All attached knowledge bodies, neighbor knowledge, unrelated graph branches |
| `global_functional` | Optional revision/pagination | Entire compact pure functional graph and provider joins (including links necessary to reconstruct address associations), optionally paged when large | Any supplementary knowledge, chats, runtime logs, inboxes |
| `local_knowledge` | Focused namespace address | Same local functional adjacency **plus knowledge attached to the focused element only** | Neighbor knowledge bodies, transitive layer dumps, unrelated graph state |

No mode is automatically frontloaded. Local results do not re-emit the entire local namespace on a one-edge change. The read can return a compact changed record/delta if the caller has a revision cursor and requests the update. Clients must be able to opt for a full view when they need it, subject to page/budget limits.

**T-002 — Semantic write operation:** `functional.apply` is one operation accepting **batched semantic forms**, not SQL/Cypher, backend table names, generated row IDs or one MCP call per discovered element. One submission can include multiple namespace element definitions and provider joins, and request additions/refinements/removal under explicit version/authority rules. Agents reason in terms of RE, PE, OP, EF, IFD and namespace addresses. The chassis translates validated semantic operations to persistent writes.

**T-003 — Batch contract.** A batch carries a stable request/block reference for idempotency; the expected graph revision when known; semantic objects; and optional source references. The chassis returns compact results: committed revision, accepted and rejected item counts, item-level validation notices, and resume reference if a multi-block job remains. It does **not** echo all input records or dump storage rows. Atomic-versus-partial behavior and conflict semantics must be fixed in the implementation contract; until fixed, no agent may assume partial success or silently retry unknown writes. Example submission in this package is labeled **PROPOSED**.

**T-004 — Extensibility.** Two tools are the baseline *functional namespace agent boundary*, not a decree that physical actuators, virtual physics, or user-specific interfaces can never have distinct protocols. A module's capability does not automatically become a new global MCP tool. MCP resources/skills and typed capability discovery remain extensible without an explosion in top-level tools. Do not import the earlier draft's seven proposed MCP operations as settled API.

## 4. Canonical Intake: preserve thinking, replace storage choreography

**I-001 — Semantic process.** Canonical Intake captures the functional type, surveys the artifact rather than merely its README, identifies AUE/AT/CQU and DE/SE/NE, finds RE-owned OPs and the PEs whose EFs satisfy them, follows dependencies recursively, audits ICE during tracing, closes blind spots, anneals only when purpose is preserved, then performs a final proof/readback and corrections. These are substantive semantic checks, not arbitrary UI stages.

**I-002 — Tool efficiency.** The old XML says to write **one object per call** during recursive reasoning. That specific output instruction is superseded by block-based semantic `functional.apply`. Reasoning may be recursive internally; writes are **batched by coherent scope**. It must be possible to observe progress, correct mistakes and resume without forcing a model call for every provider record. Do not reduce the recursive depth or eliminate a check simply because its legacy write strategy was expensive.

**I-003 — No unsafe auto-rewriting.** The original XML contains checks deliberately designed by the user; none may be deleted merely for being phrased as a constraint or sounding like a permission policy. Separate the source's legitimate functional/namespace/ICE verification from unrelated subsequently introduced authorization gates. Intake is not gated or refused for subject content; resulting maps may be graded/refined after creation, as original process states. Keep notices and discrepancies visible, with caller authority enforced at system boundaries rather than fabricated natural-language prohibitions.

**I-004 — Completion.** At closure, read the pure map, validate connectivity and the functional roots, CQU pathways, namespace rules, missing NEs, non-built status, ICE completeness, source references and annealed relationships. Return concise completion evidence and actionable remaining issues, not a misleading green score generated from unverified source checks.

## 5. Context scope, duplicate delivery, inboxes

**D-001 — Context epoch.** Distinguish durable conversation/commit history from current model context. A context epoch runs from agent orientation/compaction-handoff through the next reset. Content is delivered only once *per stable version within that epoch* when the actual body reaches the agent. Discovery and notification alone are **not** delivery. A new epoch may re-acquire what is necessary. New versions and explicitly requested refreshes are handled through versioned reads, not automatic repetition.

**D-002 — Delta on change.** When a provider join is newly attached to the agent's active node, a brief structural change reference is sufficient; upon viewing, return the changed join's provider, OP, EF, IFD and relevance, not the complete local graph or neighbor knowledge. Receipt identity is keyed to agent + epoch + content revision rather than five incompatible legacy ledgers.

**D-003 — Mailbox state.** Each agent has an inbox and each namespace element has a pending inbox intended for a visiting/eligible agent. A queued notice does not enter a model prompt by existing in storage. When someone requests/acquires a notice body, delivery and acknowledgment are tracked; after successful acknowledgment it is removed from the **pending** node inbox. Retain a read-record trace on the node and consuming agent (agent read-messages mailbox). No permanent semantic memory is created merely by delivery. Concurrent visitors must not double-consume a once-only notice; retries and failures must not lose it.

**D-004 — Explicit messaging rule.** **Absolutely no automatic informational, progress, log, completion, or generic work-event messages to model turns.** This applies to chassis events and metadata updates. Internal events remain internal triggers for deterministic state transitions. Agent-to-agent directed messages/questions, explicit assignment selection, user direction, and context handoff are distinct allowed paths. Peer communications are evaluated for relevance and avoiding under/over-communication, not replaced by supervisor-style broadcasts. Pending inbox content can be read voluntarily or surfaced as a small mailbox descriptor at arrival without injecting the full body. A normal log/event cannot masquerade as a peer message.

**D-005 — Transport.** MCP events/notifications are a forward-compatible standard **where the actual harness supports them**; the current local directed messaging mechanism remains a compatible fallback. Do not assert that all MCP clients can wake an idle model. A2A is not required for local messaging; it remains an option for independently hosted agents/remote collaboration.

## 6. Agent identity, lifecycle, orchestration and reputation

**A-001 — Persistent identity.** Each agent has a deterministic unique name and persisted identity. Runtime execution contexts may start, finish, hand off or retire without deleting the identity. Keep conversation and commit references/handoffs across contexts; do not pretend each code edit is fully captured in a conversation log. Retired identities remain addressable as historical resources to other agents/developers.

**A-002 — Dormancy and reuse.** After a task, an agent becomes idle/dormant and eligible for selection if its useful context, skills, harness cache window and remaining context budget justify reuse. Do not automatically spin up a new session for every assignment. Idle runtime memory/caching cost and harness retention are platform-specific and measured; 5 minutes was illustrative, **not** a universal retention guarantee. If the cache is gone or orientation is cheaper than restoring a heavily used context, retire the execution context from selection while retaining history.

**A-003 — Context handoff.** Existing design intent: warn about a self-handoff around 50% context use, give reasonable grace to finish work, and enforce renewal by approximately 65% subject to explicit configured policy. The new copy retains continuity through stored conversation/commit history and a compact handoff, without re-delivering all prior edited code. Preserve rather than silently replace existing engineered lifecycle checks; verify actual implementation separately.

**A-004 — Adaptive team sizing.** There is no mandatory two-agent minimum. User preferences have precedence; in Full Auto a facilitator may select one worker, a mutual-review pair, or differentiated spec/implement/test agents based on the task and namespace decomposition. A reciprocal pair checks each other's work while owning its own output. Avoid automatically creating extra review sessions or paid turns for every completion.

**A-005 — Peer reputation.** Agents evaluate peers' work correctness, critical review quality, communications (including excessive/insufficient messages) and cooperation. Other agents may inspect an agent's **aggregate reputation and skills** for selection, but the subject cannot see its **own score**, and peers cannot inspect reviewer attribution or individual peer evaluations. Scores are aggregated over assessments so one bad instance does not erase history. Exact score formula, minimum evidence and handling missing data remain outside settled contract; do not fabricate their values.

**A-006 — Optional retirement rule.** Proposed: if an agent is lowest-ranked for **two consecutive eligible assessment cycles**, mark its current runtime context ineligible for new tasks and let it go dormant; retain its identity, conversation and references. First low cycle alone is not retirement. A poor/fouled context must not keep receiving work just because the model is nominally powerful. The user retains override/control. This retirement threshold was discussed as a proposal rather than a fully specified scoring algorithm.

## 7. Chassis, protocols, physical and virtual paradigms

**H-001 — Chassis control.** Initially preserve useful Python chassis/module discovery, lifecycle, DAO ownership, transaction, event and public extension semantics; strip only proved-obsolete interface coupling. The graph backend may move toward LadybugDB; this does not license Node modules or agents to own the database or manipulate tables directly. Converting the chassis core to Rust is a **possible later selection**, not a mandate; Python remains a supported extension language.

**H-002 — Node MCP boundary.** Node/TypeScript is the preferred protocol-facing MCP module; it uses a versioned internal service interface and does not independently own storage, module registration or business rules. Current CLI and MCP serve different audiences and may expose distinct appropriate surfaces; module verbs are not automatically individual global MCP tools. MCP standards compliance is tested against actual clients/adapters, not assumed from an aspirational draft.

**H-003 — Three paradigms.** Functional position is a namespace location and direct contextual links; virtual position is a world/entity spatial pose and perceptual geometry; physical position is a device/sensor state. They share discovery/encounter/capability semantics where useful but do not pretend functional distance is Euclidean. High-rate data, robot balance, motor safety, world physics and reflex loops remain local to embodiment adapters, not LLM tool latency. Bevy/WASM is a possible virtual adapter, not an imposed world engine. Physical Microduck-style control remains lightweight over device transport.

**H-004 — Permissions and autonomy.** User commands, delegated authority and actor identity need valid authentication at the control boundary; this is not permission to insert hundreds of content gates or blanket denials into Canonical Intake. Event/subscription declarations must not accidentally cause informational model turns or high-frequency prompt flooding.

## 8. Required verification scenarios

1. **Correct schema vocabulary:** a receiver-owned provider dictionary key is a namespace address; value contains `op`, `ef`, `ifd`; no `join type=purpose`/`purpose`/`function` substitutions in new output. A PE can serve more than one RE using distinct provider joins.
2. **Read isolation:** local functional and global functional produce zero supplementary knowledge bodies; focused knowledge mode includes only the focus node's knowledge plus direct functional stubs; no transitive knowledge.
3. **Batch apply:** submit several elements and joins in a single semantic block, read them back semantically, reject or report invalid refs clearly, and demonstrate idempotent retry without duplicated joins.
4. **Retained intake reasoning:** a functional survey, CQU choice, DE/SE/NE trace, recursive dependency coverage, ICE inspection during traversal, final closure and readback remain visibly performed without a per-object command sequence.
5. **No phantom model turns:** feed 100 unrelated log/progress/completion events through chassis; **zero informational model turns**. A direct agent question may wake or reach the recipient through the approved directed communication channel.
6. **Exactly-once pending consumption:** place one message in a node inbox; two concurrent visitors must not both receive it as the first consumer. Ack removes from pending; read-record trace persists; a failed delivery stays eligible for retry.
7. **No repeated context:** same body/version in the same epoch is not re-sent on navigation; a compact delta for one new provider join does not include the whole graph; a new epoch may reacquire.
8. **Lifecycles:** one worker after completion remains eligible if cheap to reuse; a cost-expired context retires without loss of agent name/history; handoff retains conversation and commit references.
9. **Adaptive teams and reputation:** user can select one agent; full auto may choose a pair or layered roles; peers cannot read own scores or reviewer details; two-cycle retirement does not erase name/history.
10. **No backend exposure:** agent-intake payloads and prompts contain no database IDs, table schemas, SQL/Cypher, or internal migration names. Data adapter can be swapped behind semantic API without agent-facing change.
11. **Resource use:** measure paid model calls, tool count, input/output tokens, duplicate context bytes, completed functional work, latency and pass/fail rates. Do not benchmark only whether a test ran or an agent was launched.

## 9. Deliberately not invented in this candidate

Physical LadybugDB table and index schema; exact schema for *every* arbitrary module layer; atomic versus partial semantics for a failed multi-object batch; additional relationship cardinality beyond one RE/PE pair; ICE block/group encoding beyond the uploaded boolean; reputation score weighting and sampling; model-provider cache TTLs; exact protocol for global events across all harnesses; full proven catalog of legacy prompts; exact authoritative field rules for universal element-level `op` and `ef`. These require narrow design decisions; **their absence must not be repaired by silently adopting old code or previous drafts**.
