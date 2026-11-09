# Proposed specification amendments and extraction order

Status: review proposal. Owner decisions below already govern this review. Proposed mechanisms and acceptance checks remain proposals. The existing archive is preserved. This document does not establish implementation readiness.

## Why

Retain useful Metaform mechanics while replacing the agent experience and persistence assumptions that conflict with the rebuild. The ECS packet is the starting ground truth. The owner's amendments update that ground truth without reopening product discovery or LadybugDB selection.

## Capabilities and preserved identities

Preserve archived CAP-1 through CAP-16, AC-01 through AC-16 and D-01 through D-19 identifiers. Do not renumber them or silently adopt archived review suggestions as owner decisions. Changes below refine their contracts. All other capability outcomes remain in force, including ICE composition, addressed communication, history, reputation privacy and revision-bound documentation.

| Existing record | Governing owner decision | Specification change required |
| --- | --- | --- |
| CAP-1, CAP-2, D-04, agent-interface.md:7-13 | A/C: functional meaning persists, implementation and choreography may change | Replace any reading of “preserve the reasoning procedure” that freezes existing intake steps. Preserve RE-owned OP/EF, IFD, meaningful Addresses, canonical names and references while supporting coherent submissions and revision. |
| CAP-2, AC-02, completion-work.md:7-11 | A/C: semantic MCP is a primary redesign | Specify a complete intake → readback → refinement journey before choosing final operation names. Storage keys, closure edges, graph publication and process-lock choreography remain behind the interface. |
| CAP-3, AC-03, D-06 | C: three distinct retrieval presentations | Specify local functional, global functional without ancillary layers, and local knowledge-rich with direct relationships and only the selected element's applicable knowledge. Keep movement distinct from inspection. |
| CAP-5, CAP-6, AC-05/06, D-07/14 | C: discovery, resource delivery, skill loading and retained context differ | Preserve source/version identity and once-per-epoch delivery with deltas. Record each observable boundary. Report unobservable retention as unknown. A receipt is never comprehension. |
| CAP-8, CAP-13, D-03/13/18 | D: capability/version-selected draft MCP events, general local fallback | Replace ECS technical §7.4's exclusion of the draft mechanism as a blanket design choice. Use the supported draft on capable harness versions, chassis-local events/messages otherwise, through a common semantic event contract. Codex is owner-identified as the current supporting harness. Verify the actual deployed version/binding. |
| CAP-8, AC-08, lifecycle-and-delivery.md:3-9 | D: purposeful communication is allowed, routine live logging is excluded | Preserve assignments, peer messages and reasoned events. Keep stored ticket/progress diagnostics out of automatic model-context streaming. Do not enforce this with an invented event allowlist, participant hierarchy or mandatory reviewer pipeline. Preserve explicit dynamic blacklists. |
| CAP-12, AC-12, ECS technical §2.3/4/10.1 | B: LadybugDB and a different model across retained state | Extend compatibility work to project registry/settings, prompts and versions, agent identity/session/conversation state, delivery receipts, messages, event journals and orchestration records. Metaform-owned durable state uses the selected LadybugDB arrangement with explicit record/version/transaction contracts. References to externally owned native resources do not permit an internal settings/session/receipt SQLite exception. |
| CAP-8/10/13, ECS technical §3/7/10 | E: asynchronous Python–Node.js channel required | Add an explicit channel contract for sessions, streams, cancellation, state, failures, reconnects and event routing. ACP placement remains an open Python-versus-Node ownership decision. The hosted Metaform Node/broker name proves neither a Node.js runtime nor an inter-runtime channel. |
| CAP-14, AC-14, D-16, ECS technical §8/9/12 | F: physical and virtual profiles have distinct geometry/ranges | Replace the common axial-depth-only success criterion at archived SPEC.md:78-80. Preserve a physical camera/depth-grid profile up to 3500 mm at 60° FOV. Add virtual 360° sensing as eight spherical wedges with top-to-bottom distribution, event zone of 45° plus up/down angle, query-at-any-time access and full unsigned 16-bit millimeters through 65535. Virtual space may also expose the conventional 3500 mm/60° array profile. |
| CAP-14, AC-14, ECS technical §9.1 | F: sensing is a data/control surface | Agent-written code may trigger events and initiate actions. Rear-event → head-turn → image/depth read and forward stealth-NPC sensing are example consumers. Do not require either reaction, autonomous detection or gameplay policy. Local action independence is an available mechanism, not compulsory NPC behavior. |
| Reuse/extraction plan | A/B: chassis specification and Python module template are permitted reuse sources | Preserve those foundations while evaluating their public and transitive persistence contracts. Recover September Ladybug work as evidence. Permission is not proof of unchanged backend compatibility. |

Archive-relative citations above mean `next_spec/metaform-specifications-2026-10-28.zip!metaform-specifications/<member>`. ECS references mean `ecs/Inference-Metaform-ECS-Terminology-Review.zip!03-technical-specification.md`. Digests and member identities are in [SOURCE-MANIFEST.json](SOURCE-MANIFEST.json). The governing source is [OWNER-AMENDMENTS.md](OWNER-AMENDMENTS.md).

## Constraints

- Preserve **C(T) = { (r_i ∧ p_i ∧ e) }**, receiver ownership and the distinct meanings of OP, EF and specification Objective Purpose. Namespace ancestry, functional relationships and spatial geometry remain separate.
- Keep requirements distinct from observed implementation, tests read, tests executed, historical results and proposed acceptance checks.
- Every extraction recommendation requires behavior and transitive dependency evidence. A familiar public interface, passing SQLite test or engine-name match is insufficient.
- Maintain direct addressed access, explicit unknown/empty/partial responses, source revisions and coherent revision outcomes without grading semantic judgment in deterministic code.
- Retain the archive's existing D-19 exclusion of `visible_up` attachments from applying projections. It remains an explicit correction, not a newly reopened design point.
- No wholesale code migration, new runtime SQLite persistence, fixed event allowlist or inferred approval hierarchy follows from this review.

## Reviewer proposals to complete the contracts

These are engineering proposals, not newly settled owner decisions.

1. Define a semantic change result that returns the represented objects, stable relationship references, resulting revision, unresolved references and retry outcome. Let a related-object submission be small enough for incremental reasoning. Specify whether the coherent change is atomic and how partial rejection is reported. Keep exact tool and field names provisional.
2. Define projection records separately from delivery records. A source cut identifies what was selected. A delivery record identifies what bytes crossed which harness boundary in which epoch. A loaded-skill record requires the actual skill-loading path. A retained record requires observable harness evidence.
3. Define one graph/publication service boundary covering base snapshots, derived ancestry/incidence and runtime records. Complete transaction/write-queue behavior on the selected LadybugDB version before extracting storage-dependent chassis services. A proposed queue is storage serialization, not a hierarchy among participants.
4. Define a general semantic event envelope and transport adapters. Keep source identity, causation, target, source/journal sequence and payload meaning stable. Sensor observations belong to a sensor payload/profile, rather than making every peer message carry fabricated sensor fields.
5. Define channel/session state ownership once for either ACP placement. Separate transport reconnect from native session resume and command retry. Preserve uncertain outcomes after a lost completion. Keep the wire/protocol choice open until the ownership comparison is resolved.
6. Version the sensor profiles explicitly. Specify angular zero, positive rotation, vertical-angle convention, zone boundaries, frame transforms, observation quality and no-return representation for surround sensing. These details are required engineering completion. Do not choose arbitrary values here or impose forward positive-z/axial-z geometry on surround data.

The concrete interaction proposals are in [COMMAND-CONTEXT-INTAKE.md](COMMAND-CONTEXT-INTAKE.md). Runtime, channel and sensor boundaries are in [RUNTIME-AND-EVENTS.md](RUNTIME-AND-EVENTS.md). Storage and recovered-code evidence are in [BACKEND-COMPATIBILITY.md](BACKEND-COMPATIBILITY.md) and [SEPTEMBER-LADYBUG-RECOVERY.md](SEPTEMBER-LADYBUG-RECOVERY.md).

## Dependency-ordered refinement and extraction plan

| Order | Review/specification output | Dependency and completion condition | Later extraction implication |
| --- | --- | --- | --- |
| 1 | Source and requirement crosswalk | Pin main and archives, retain amendments, freeze independent reports and reconcile disagreements | Candidate files have stable evidence. No historical assignment becomes executable work. |
| 2 | Semantic intake/change and readback contract | Work through one creation, one relationship revision, one unresolved reference and one retry, plus all three retrieval presentations | Determines the semantic interface before reusing command declarations or intake handlers. |
| 3 | Target persistence contracts | Map every retained service to snapshot/live records and define IDs, row/result replacement, transaction boundaries, write serialization and conflict outcomes | Recover historical Ladybug driver/query patterns selectively. Replace current SQL-shaped storage and SQLite-owned runtime paths. |
| 4 | Public chassis/template boundary | Use stage 3 to decide the replacements for database/schema hooks, settings/prompt history, owned tasks and module lifecycle | Preserve declarations, packaging, validation and template teaching mechanics that meet the new contract. Adapt examples and compatibility declarations together. |
| 5 | Context projection and harness delivery contract | Combine stage 2 views and stage 3 versioning with explicit delivery/skill/epoch observability | Extract version/digest, exact rendering, coalescing and receipt mechanics behind new persistence and delivery boundaries. |
| 6 | General events and Python–Node/ACP contract | Keep semantic envelope independent of transport, define capability/version negotiation, failure/reconnect and a single session-state owner | Adapt bus/relay/lifecycle mechanics. Add the required async runtime channel only after its contract and ACP ownership are resolved. |
| 7 | Profile-specific sensor contract | Apply F to observations and events, preserve on-demand reads and consumer-controlled actions | Reuse observation provenance/quality ideas. Replace forward-only assumptions for surround sensing. No autonomous NPC implementation follows. |
| 8 | Focused acceptance specification | Separate unchanged legacy protections from new target-engine/harness/channel/profile demonstrations | Implement only under a subsequent assignment. Keep ICE-coupled shared interfaces together when later planning extraction slices. |

Stages 3 and 4 refine each other at the public-base boundary. Stages 5 and 6 share identity/epoch/event state. These are dependencies to resolve, not a demand for a large all-at-once rewrite.

## Proposed acceptance additions

- AC-02/03: model-visible semantic intake and revision require no SQL/Cypher, generated storage IDs or procedural database commands. Readback preserves OP/EF/IFD and unresolved source references. Neighbor knowledge cannot appear incidentally in the local knowledge-rich result.
- AC-06: inspect exact rendered bytes and effective prompt/role versions across read, move, edit, compaction, handoff and dormant resume. Separate known delivery, known skill loading and unknown retention.
- AC-08/13: deliver the same purposeful peer/assignment/sensor event over a supported draft path and a local fallback, retaining origin and identity. A version change alters the adapter, not the producer. Routine unrelated ticket/progress traffic creates no automatic harness-context stream.
- AC-12: execute snapshot/derived-topology publication and runtime-state operations on the selected LadybugDB version. Verify retry/conflict behavior and failure recovery. Check that retained settings, conversations, sessions and receipts do not open SQLite runtime databases.
- AC-13: lose the Python–Node connection before submission, after native submission and after completion-before-ack. Distinguish never submitted, pending, completed and unknown outcomes. Cancellation and reconnect do not silently create another turn or session.
- AC-14: distinguish physical 3500 mm/60° camera/depth overlay, virtual conventional array and virtual surround profiles. Query all eight wedges, test rear/top/bottom and 45° boundary events, and preserve values 32767, 32768 and 65535 without signed truncation. Invalid/no-return state stays separate from a valid maximum-range value. No event forces a head turn or gameplay action.

These checks were not implemented or executed by this review.

## Non-goals

Rebuild implementation, data migration, tests added for the rebuild, old prompt edits, database reselection, product rediscovery, a final ACP placement, a final MCP operation inventory, autonomous NPC policy, a mandatory team/reviewer hierarchy, or a claim of implementation readiness.

## Success signal

The owner can identify the specific foundations to preserve, the boundaries that require adaptation, the interfaces to re-engineer and the decisions still localized to ownership or evidence. A subsequent implementation assignment can use the ordered contract work without repeating this review or treating legacy behavior as the target by default.

## Narrow open decisions and evidence gaps

- ACP owner: Python or Node, using the sessions/streams/cancellation/recovery comparison in RUNTIME-AND-EVENTS.md.
- Final semantic request/result/error schemas and exact operation names, including coherent-change atomicity and version-aware retries.
- Deployed Codex version and draft event capability/binding, plus measured behavior of each additional harness profile.
- Surround angle/frame/sample conventions and physical calibration data. The required topology/ranges and example-policy distinction are settled.
- Target-engine execution and harness/channel interoperability proof. Historical Ladybug code and archived schema fixtures do not supply this proof.
- Existing localized reputation arithmetic/cycles and proposed retirement-rule details remain in the archive's completion queue. This review does not change their status.
