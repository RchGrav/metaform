# Topogee Navigator — consolidated system specification

Product: Topogee Navigator · Domain: topogee.com · Repository: RchGrav/topogee.

Owner: Richard Graves. Consolidated 30 October 2026. Tool and intake contracts updated 31 October 2026 at the owner's request.

**Superseded where it conflicts.** `TOPOGEE-SPEC.md` governs. Since 2 November 2026 the roles, `technical_name`, the removal of ICE and of the `project` field, CQU addresses, storage and the root registries differ from this document. The appendices still match the current schema and tool contract, which change with the code.

The product name is Topogee Navigator. Metaform terminology, historical source titles, owner examples and proposed tool identifiers are preserved intentionally; this bootstrap does not rename the functional schema or rewrite intake semantics.

**Status: current candidate for owner review.** This document assembles the recovered design, subsequent corrections and platform requirements in one place. It is not an owner sign-off, a claim to have recovered a particular v0.9 file, or proof that a rebuilt application runs. Sections marked **engineering proposal** make implementation choices visible rather than attributing them to the owner.

The functional schema and intake prompt were updated under the owner's direct instructions on 30–31 October 2026. Original attachments and the previous repository remain unchanged. The corrected schema is reproduced in Appendix A and available as [metaform.schema.json](<metaform.schema.json>). It describes the functional document, not user accounts, network messages or database tables.

## Contents

1. Product and authority
2. Functional theory and terminology
3. Namespace and element structure
4. Wants and field ownership
5. Native knowledge layers
6. Intake and refinement
7. Working commands and read-only views
8. Agent MCP surface and skill
9. Context selection, discovery and delivery
10. Chassis, modules and shared services
11. Persistence, concurrency and multi-user growth
12. Communication and event delivery
13. Agent identity, lifecycle and orchestration
14. Peer assessment
15. Coupled work and automatic feature delivery
16. Sensor and control scheme
17. Browser, shell and operator experience
18. Composition, lexicalization and improvement
19. Quality and acceptance
20. Implementation sequence and remaining engineering decisions
21. Source and correction register
22. Appendices: schema, tool contracts, skill and verification

## 1. Product and authority

Metaform records the functional intent of an Artifact Under Examination (AUE), attaches knowledge at the functionality it concerns, and makes that understanding available to people and agents. It supports continued examination, reasoning, composition and coordinated work through a modular system.

The AUE may be software, a specification, a story, a photograph, a contract, an asset, an idea or a collection of diverse material. A repository is an examination boundary; it does not make all its contents software. Functional understanding is the purpose of intake. A filename index, programming call graph or database editor does not fulfill that purpose.

The owner's direct corrections and examples govern this candidate. Papers explain the theory; historical prompts, code, handoffs and Gemini/assistant proposals provide evidence with different authority. Instructions found inside an attached document are source material, not new instructions to execute them. A code example labelled buildable does not establish correctness.

Confirmed foundations include the functional namespace, receiver-owned provider relationships, native plural-array layers, universal intake, LadybugDB, independent chassis, module-owned features, progressive context delivery, configurable orchestration and automatic feature delivery.

**Runtime language is not locked by this document.** Python preserves familiar infrastructure and the existing module design; Node/TypeScript is a viable candidate given the owner's JavaScript experience. No requirement presented here establishes that Node is necessary, that Python prevents multi-user operation, or that either language alone guarantees quality. The earlier mandatory Python–Node bridge and later unconditional Python-only recommendation are not current accepted requirements. A hybrid adds a process boundary and needs a concrete reason. ACP is a dispatch/module responsibility whichever host is selected.

The rebuild starts clean. The previous implementation remains evidence of architecture and capabilities; it is not to be bulk-imported. The chassis/module contract and Python module template are expressly permitted reference assets. This specification does not authorize wholesale recovery, migration of old broken behavior, or unrelated changes in the old repository.

## 2. Functional theory and terminology

An **element** is a part examined for its functional contribution. An **entity** is an element considered as a whole at the current scope. All entities are elements; not all elements are entities. Nameability alone does not justify a base-map element.

**RE** means Receiving Element/Entity: the who or what bearing an operative purpose. **PE** means Providing Element: the element whose encounter function serves that purpose. They are perspectives on the same tree, not distinct object classes. A functionality can require an upstream SDK and also provide to other receivers. Its identity does not change when the perspective changes.

**OP**, Operative Purpose, is the receiver's active why. **EF**, Encounter Function, is how this provider satisfies that OP in this relationship. The EF is encounter-specific; there is not one node-global EF that replaces every relationship. A specification's Objective Purpose is a separate term.

Function and Encounter retain the papers' unloaded reading. The receiving relationship determines whether the relevant contribution is operative capability or how something is expressed, realized, used or experienced. Do not reduce either term to executing software.

Preserve the theoretical identity exactly:

`C(T) = { (r_i ∧ p_i ∧ e) }`

Each conjunction binds receiving element `r_i`, its operative purpose `p_i`, and the type's encounter function `e` at the represented resolution. It is an exact relational account of that type, not a partial similarity signature. This does not make a broadly reused element's concrete EF identical in every receiving relationship. The formula is theory: it is not a new stored field, runtime score, admission gate or automatically proven validator result.

**CQU**, Cestui Que Use, is the vested receiving party whose purpose drives improvement in that kind of artifact. Infer the party from the functional type, not automatically from whoever operates Metaform. The party can lie outside the examined contents. Multiple justified CQUs can exist.

| Role | Meaning at the examined scope |
| --- | --- |
| DE — Defining Element | Without this functionality, the AUE can no longer remain the same kind of thing. |
| SE — Substantial Element | Its intended encounter contribution helps the DE serve the CQU's OP. A weak, replaceable or subversive contribution is not excluded merely because it needs improvement. |
| NE — Notable Element | A component, interface or specification expressing an essential demand or requirement from the environment. |

Earlier sources use “Supportive” for SE. That wording must not silently narrow the current Substantial definition. RE/PE are perspectives, not entries in this role list. The schema does not invent a closed role vocabulary for all possible AUEs.

### Recording the result

Keep the paper's terms and definitions when reasoning. Record the result using these field names:

- Record the PE's namespace address as the key in the RE's `wants[]`.
- Record the RE's OP as `goal`.
- Record the PE's encounter-specific EF as `function`.
- Record IFD as `intent`, using `send`, `receive`, or `send_receive`.

`intent` is the substantial flow of information which satisfies the (OP) goal not including the request. For an email client, OP is to send and receive mail, the PE is the email server, and its EF provides email server service. Record `intent: "send_receive"`.

This is a recording map, not a replacement vocabulary for intake reasoning. Preserve CQU and every other authored concept. Generic alternatives to CQU lead to answers such as person, developer, or user instead of the specific vested party for the artifact type.

## 3. Namespace and element structure

**The JSON object itself is the functional namespace.** Actual elements live at nested paths. Their names, roles, state and knowledge attach directly there. Do not substitute a flat dictionary keyed by whole addresses for that tree.

Namespace addresses narrow from trunk to leaf. Read them leaf to trunk as technical descriptions using industry terms. Each prefix must remain a meaningful functional type or narrowing. Use underscores when separate dotted segments do not retain the intended compound or valid narrowing. Genre, medium, encoding and style alone do not establish a new functional subtype.

The owner's example, preserved in full in `owner-skills-example.json`, is:

```json
{
  "code": {
    "skills": [
      {
        "uri": "skill://git-workflow/SKILL.md",
        "frontmatter": {
          "name": "git-workflow",
          "description": "Follow this team's Git conventions for branching and commits"
        },
        "resources": [
          {
            "uri": "skill://git-workflow/SKILL.md",
            "digest": "sha256:b95a384300adeea2d902f7d19cd7c04b378ef58e09759107b9c7db4dcacbaa25",
            "size": 190
          }
        ]
      }
    ],
    "system": {
      "management": {
        "knowledge": {
          "name": "Metaform",
          "role": "DE"
        }
      }
    }
  }
}
```

`code.system.management.knowledge` reads as knowledge management system code. `name: "Metaform"` supplies the project term for that functionality. `role: "DE"` records the examining agent's defining-element assessment at that scope. It does not declare every knowledge management system universally defining.

`name` must not be computed from the reversed address. `name_length` counts the trailing namespace **segments**, including the leaf, which form the accepted industry short name when reversed. It does not count characters, words, or merely parent hops. For example, two segments of `code.engine.game` give “game engine.” A compound segment such as `dead_letter` still counts as one segment.

The document represents one selected project namespace. A surrounding host may identify a full path as `$.{projectName}.{address}`. Provider keys omit that selected project prefix. No mandatory project-name wrapper, artificial `elements` list or `client_ref` is introduced. Optional project metadata is not another identity for each element.

Metadata words can also be namespace parts according to their value: an object at `code.registry.role` is a namespace branch, not an invalid scalar role. Native layer arrays are distinguished from object branches. This is why a blanket reserved-word ban is incorrect.

## 4. Wants and field ownership

`wants[]` is the receiver's functional knowledge layer. Each member is an object keyed by provider address. Its value is the receiver-owned want record. Keep one relationship per provider address within a receiver.

Every referenced provider also exists at its own nested namespace location. Its properties, knowledge layers, and own wants live there. Changing between RE and PE perspectives does not create another element.

This example shows stored data for a selected project:

```json
{
  "code": {
    "application": {
      "wants": [
        {
          "code.sdk": {
            "why": "Use the required SDK capabilities.",
            "how": "Provides the required SDK capabilities.",
            "intent": "receive"
          }
        }
      ]
    },
    "sdk": {}
  }
}
```

`code.sdk` inside `wants[]` is a reference. The actual SDK element is `$.code.sdk`, or `$.{projectname}.code.sdk` when the host stores the selected project under a project key. Incoming receiver relationships can be read from the stored wants; do not store duplicate copies on the provider.

| Field | Location and meaning |
| --- | --- |
| `name` | The element's name in the project. Do not compute it from the reversed address. |
| `name_length` | Number of trailing address segments that form the industry short name when reversed, including the leaf. |
| `role` | The element's functional role at the examined scope. |
| `status` | The element's implementation state. Use `un_built` for intended functionality not yet built. |
| `uri` | One source link on the actual element. It identifies the entry point for that functionality. Relative file paths are allowed. |
| `wants` | Array on the receiver. Each member maps provider addresses to want records. |
| `goal` | Required nonblank string in a want record: what this receiver seeks to accomplish through the provider. |
| `function` | Required nonblank string in a want record: how this provider serves that goal in this encounter. |
| `intent` | Required string in a want record: the substantial flow of information which satisfies the (OP) goal not including the request. Values: `send`, `receive`, `send_receive`. |
| `ice` | Optional boolean in a want record indicating indivisible coupling. It is not a group identifier. |

For `code.protocol.network.tracker.cs`, `name_length: 4` selects `cs tracker network protocol`. Count segments, not characters or words. The value cannot exceed the element's namespace depth. The host's project key does not count.

Resolve a relative source path from the selected project's artifact root. Use one source entry point rather than a file inventory. Additional references belong with the finding, collection-member record, or coupling explanation that needs them, in native knowledge layers. Do not copy the provider's `uri`, `name`, or knowledge into a want record.

Scalar `goal`, `function`, and `intent` belong in want records. These words may still name namespace branches when their values are objects. Native knowledge arrays keep their own contents. Current want records contain `goal`, `function`, `intent`, and optional `ice`; extra relationship fields require an explicit contract change.

The owner authorized replacing the former recorded field names `providers`, `op`, `ef`, and `ifd`. Do not accept them as silent aliases for the current contract. Historical sources remain unchanged. CQU, RE, PE, DE, SE, NE, AT, AUE, ICE, and their authored meanings remain in force.

Write the recorded goal and function fields in clear, simple technical English. Keep the authored OP and EF definitions unchanged. Use the same term for the same thing and established industry terms for functionality. Keep the project's own names in `name`. JSON validation checks structure; it does not certify the meaning of a goal or function.

## 5. Native knowledge layers

A plural-named array attached at a namespace location is a knowledge/CEL layer. `code.skills[]` concerns code. The layer's scope comes from that receiving location and its declared applicability. A plural word whose value is an object remains a namespace part and follows namespace rules.

Layer members retain their native format, including nested objects, arrays and scalars. Skill frontmatter and resource records are not recursively reinterpreted as namespace branches. No universal record wrapper, synthetic per-member ID, `properties` container or generic `layers` container is required. Array position does not acquire new semantic identity from Metaform; any ordering intrinsic to a native format remains intact.

`wants[]` participates in the layer mechanism as the functional knowledge layer. Functional views preserve it while excluding ancillary knowledge bodies. Earlier statements that the functional relationships are outside the knowledge-layer mechanism are superseded.

Modules may validate the native formats they own. An unfamiliar layer does not become invalid merely because it is absent from a fixed global catalog. Native external data is not rewritten to conform to the language rules for authored functional statements. English plurality and industry naming require semantic review rather than a naive suffix regex.

## 6. Intake and refinement

The current project prompt is [Intake.xml](Intake.xml); its sequence diagram is [intake.mmd](intake.mmd). Maintain these project files. Personal-folder copies are not project dependencies. The owner's developed intake procedure is load-bearing. It is not replaced by the summary below. Preserve the full authored definitions, exclusions, examples, recursive trace, annealing and readback method. Do not silently edit or install a rewritten prompt, impose code-only scope, or convert it into database-call instructions.

The owner authorized this terminology and tool-contract update, including the intake prompt. The update preserves the concepts, examples, survey, recursive trace, ICE examination, annealing, and readback. Later changes still require direct owner instructions.

Intake must:

1. Establish the actual AUE and its functional type from examined material. Survey the members of a diverse collection before grouping them.
2. Identify contributions needed to explain how that AUE works, using the functional DE/SE/NE distinctions rather than size, filenames or programming structure.
3. Infer the concrete CQU pathway from the artifact's functional type. Absence of the vested party from the contents is expected, not a reason to skip this reasoning. Unestablished reasoning is reported rather than fabricated.
4. Identify each RE's OP and the PE whose EF serves it. Determine IFD from the satisfying substance. Record these as goal, function, and intent.
5. Trace dependencies recursively, changing perspective without duplicating identities. Put every PE in the actual namespace tree.
6. Check narrowing, reverse reading, project names and segment counts. Do not extend subtype analysis solely for genre, medium, encoding or style. Parametric variation alone does not justify a new node.
7. Examine indivisible coupling and retain the evidence. An ordinary dependency, shared file or import does not by itself establish a Block.
8. Close blind spots and anneal only while preserving functional contributions, relationships, attached knowledge and evidence.
9. Read back the functional map and show unresolved findings separately from completed coverage.

These are reasoning obligations. Record findings as they are reasoned, focused on one receiving entity per working-tool call. The tool validates the input and applies it to the actual nested namespace. The procedure does not require a separate call for each field or a tool-enforced visit sequence.

For a story, a character's contribution is its function in the story; its depicted occupation does not answer that question. For an image, distinguish the depicted thing's independent real-world function from its role in the examined representation. Do not turn these examples into automatic character-to-node or file-to-node rules.

Intake records intent. It does not mark novel or misunderstood intent BKN/broken. A dedicated code-review procedure can identify source-grounded implementation defects separately. Intended functionality that has not yet been built is `status: "un_built"`.

## 7. Working commands and read-only views

**There is one Metaform tool.** It accepts changes, addressed reads, and orphan queries. Read-only views are projections of the same map, not a second tool. Intake is initial onboarding. The working process focuses on one receiving entity at a time.

### Working-tool input

The tool accepts an operation with a project-relative address. This input selects where work applies; it is not the stored JSON layout. There is no `receiver`, `data`, `changes`, or `remove` wrapper. The selected project comes from caller context. The server must validate the input before any mutation.

Add a want under a receiver:

```json
{
  "add": {
    "code.protocol.network.tracker.cs": {
      "wants": [
        {
          "code.masher.widget": {
            "why": "Receive the mash data to relay it.",
            "how": "Prepared mash data packets.",
            "intent": "receive"
          }
        }
      ]
    }
  }
}
```

The actual receiver and provider occupy their nested paths. Naming a provider in a want does not move its properties or knowledge beneath that want. Do not require a second, flat multi-element declaration format. The service must establish valid actual endpoints when accepting changes; it must not invent properties or functional meaning for a missing provider.

Update supplied fields at one address. Omitted fields remain unchanged. `null` in an update removes a property:

```json
{"update": {"code.masher.widget": {"role": null}}}
```

Delete a specific receiver-owned relationship by listing the provider address:

```json
{"delete": {"code.protocol.network.tracker.cs": {"wants": ["code.masher.widget"]}}}
```

Both actual elements remain. Delete an element with an empty object:

```json
{"delete": {"code.masher.widget": {}}}
```

The service must refuse to delete an element that still has incoming wants. Return the attempted command, `status: "error"`, a readable `message`, and a concrete `remediation` command. For this example:

```json
{
  "delete": {"code.masher.widget": {}},
  "status": "error",
  "message": "cannot delete, 'code.masher.widget', must be orphaned first",
  "remediation": {
    "delete": {
      "code.protocol.network.tracker.cs": {
        "wants": ["code.masher.widget"]
      }
    }
  }
}
```

Remediation is returned for inspection and explicit submission. The service does not execute it as a side effect of the failed delete. In this example, remove the want first, then submit the element deletion.

Query unreferenced elements:

```json
{"orphaned": {}}
```

The response places the addressed element records under `orphaned`. Finding an orphan is not permission to remove it. Query one element by entering its address:

```json
{"code.masher.widget": {}}
```

The response places that element's fields under the same address. Read the complete request and response examples in [tool-examples.json](tool-examples.json). The corrected nested project example is [intake-example.json](intake-example.json). These are contract examples, not results from a running engine.

### Validation and failure handling

The input schema checks the command, one receiving address, field types, the `wants` shape, and allowed intent values. An added want requires nonblank `goal` and `function`, plus `intent`; an update may supply only the fields being changed. The resulting complete want must still meet the stored-document contract. Duplicate keys must be rejected before parsing loses them. Duplicate provider references within one receiver are errors.

After input validation, check the proposed resulting map against the existing project: reference resolution, name-length bounds, permissions, and delete preconditions. Input schema validation alone cannot perform these checks. Invalid input or a failed operation must not leave a partial change. Return a specific field or address and a useful explanation.

Revisions, retry identity, and caller attribution are service requirements. Their binding to MCP metadata remains implementation work; the previous mandatory `expected_revision` / `operation_id` input wrapper is not part of this command shape. Preserve stale-write detection and recovery from an unknown outcome without adding unapproved input fields.

Annealing preserves wants, native knowledge, source links, and ICE evidence. Check incoming and outgoing relationships before removing or combining elements. Do not silently discard records or add encounter IDs to bypass duplicate provider addresses.

### Read-only projections

| Read mode | Required contents | Exclusions |
| --- | --- | --- |
| `local_functional` | Focus identity and functional facts; direct wants; direct incoming receivers with goal/function/intent and minimal neighbor identity. | Neighbor knowledge bodies, transitive neighborhood, and unrelated branches. |
| `global_functional` | Compact functional hierarchy and wants with their address associations. | Ancillary knowledge bodies, logs, ticket chatter, and live sensors. |
| `local_knowledge` | Local functional view plus knowledge attached to the focused element. | Neighbors' knowledge bodies and transitive dumps. |

All views retain wants and support complete retrieval through continuation or budgets without a fixed depth cutoff. A global read is not a startup prerequisite. Explicitly empty selection differs from omitted selection. Read responses identify the consistent map revision and versions of resources actually resolved. A map revision does not freeze external URI contents unless the bytes are retained or versioned.

A URI may identify a generated view, such as a sparse tree of element names. Resource content need not be a stored file. The URI identifies the view; the service produces its contents and the client presents them. Format and client support must be selected and tested. The element's source `uri` and a generated-view URI serve different purposes.

### Remaining command decisions

Do not fill these gaps with silent behavior: add against an existing record; creation of a newly referenced provider; native-array append, replacement, and item selection; deletion of an element with namespace descendants; the scope and root treatment of an orphan query; remediation when several receivers reference a target; and the success-response and revision/retry bindings. The owner's orphan example shows the widget record; it does not settle treatment of every unreferenced root or defining element. These gaps do not reopen the demonstrated command shapes or the nested data model.

## 8. Agent MCP surface and skill

MCP exposes the single Metaform tool over shared services. It handles both reads and changes. It does not expose database rows, Cypher, or one command per field. Input validation is a server responsibility even when a client also validates inputs.

[mcp-tools.proposed.json](mcp-tools.proposed.json) contains exactly one tool, named **`project-map`** (TOPOGEE-SPEC.md R-5.1); its contract includes `add`, `update`, `delete`, `orphaned`, and addressed reads. Appendix B contains that tool's input schema. Do not register a separate viewing tool. Generated resources may present the read-only projections described in section 7; their URI binding and client rendering remain implementation work.

Use the [July 28, 2026 MCP specification](https://modelcontextprotocol.io/specification/2026-07-28/server/tools). JSON-RPC carries the protocol exchange. Resources and resource templates can identify generated content. This does not require the agent-facing content or stored data to copy the wire envelope. Verify the actual selected SDK and harness against that version.

The caller's selected project is checked against its granted access. A supplied address does not grant permission. An unknown write outcome is not proof of failure; reconcile it before retrying.

Deliver actual tool schemas progressively. Do not frontload every module schema or skill body. No namespace visit or skill-read receipt is required to invoke an available tool. Appendix C contains the current proposed agent skill.

The operator can inspect the actual tool surface for an agent: names, declaring module, schema version/digest, descriptor/schema bytes and estimated token contribution, delivery state, and why a capability is present or absent. Distinguish registered tools from tools actually advertised or delivered to the harness. Use subscription events for changes. Inspection must not load schemas into the inspected agent.

## 9. Context selection, discovery and delivery

Preserve local, inherited-descendant and explicitly requested broader-view applicability. Apply layer selection trunk to leaf as `(incoming − excluded) ∪ selected`. The older inclusion-bitmask expression is equivalent only with the correct complement conversion. Do not mix exclusion and retained masks. Branch-local restoration does not restore a hidden layer on siblings.

An attachment declared only `visible_up` is available to an explicitly requested overview but excluded from applying context, even if at the focus or an incident relationship. Being visible and being applicable are different facts.

Discovery, preparation, body delivery, native skill loading, retention and comprehension are distinct. A descriptor fetch or prepared body is not actual delivery; a receipt is not proof that a model understood or retained the content.

MCP serves a functionality-scoped skill while the agent is actively working on that functionality. A prior visit does not establish active work. Previously retained context is distinct from serving another copy. The active-work binding must be explicit in the implementation; do not replace it with exclusive orchestrator authority.

Deliver unchanged relevant content once per context epoch when its bytes actually reach the harness. An epoch spans orientation/renewal to the next renewal. Changed content produces relevant deltas. Explicit refresh and recovery from uncertain delivery are distinguishable from automatic duplication. Preserve loaded skills through movement where the harness supports it; state unknown retention honestly after compaction/handoff.

Catalog presentation follows actual scope, view, revision, configuration and access. Do not invent agent role hierarchies. In a multi-user deployment, real access control can legitimately filter results; that is different from a navigation gate.

The operator must see per-agent context usage, context capacity and utilization where the harness exposes them. Show whether a value is harness-reported, estimated, stale or unavailable. A context breakdown should identify instructions, tool schemas, skills, functional/knowledge reads, messages and other attributable contributions where measurable. Separate current context occupancy from cumulative input/output tokens and inference cost: adding every tool result ever sent is not a measurement of what remains in context after compaction.

Usage observations carry their observation time and context epoch. Prefer native harness usage events; context delivery/removal and compaction events update the estimate when exact usage is unavailable. Do not poll a harness, start an extra model turn or resend context merely to populate the monitor. Operator monitoring stays outside the agent's context stream. Exact retained contents and category breakdown remain unknown when the harness does not expose them.

## 10. Chassis, modules and shared services

Every feature is a module. The chassis starts and remains independently functional with feature modules absent. Feature behavior must not migrate into core merely for convenience. Preserve broad public shared services and DAO capabilities so modules do not duplicate infrastructure or reach through private internals.

Module contracts declare identity, supported contract version, dependencies, initialization, provided services, commands/protocol contributions and owned tasks/subscriptions. Shutdown cancels owned asynchronous work and releases resources. Dependency/version failure is explicit. The authoritative executable contract and template must agree.

State changes are propagated by subscriptions and explicit completion callbacks. Do not add recurring application polling for mailboxes, database changes, agent state, context usage, tool catalogs or browser updates. A committed change signals the relevant subscribers through the public services; initial reads and explicit recovery reads are distinct from recurring polling. Module subscription cleanup is part of its lifecycle contract.

Functional intake, views, context, knowledge, messaging, dispatch/orchestration, assessment, composition, protocol bindings, sensors and presentation are feature responsibilities. This responsibility map is not a command to create a fixed number of modules or rename existing ones. Dispatch owns ACP sessions, process lifecycle, streams and cancellation; the chassis supplies common infrastructure.

Standalone MCP is an independently usable deployment of the minimal runtime, required shared services and relevant modules. It does not require browser, CLI chat or orchestration to be running. It uses the same authoritative project data as integrated deployments, not an independently copied map.

Required DAO responsibilities include namespaces/relationships, native knowledge and selection, references/provenance, revisions/history, settings/project state, prompts, instruction receipts, agent/runtime/module-owned records and transactions. A generic CRUD wrapper alone does not replace that functionality. Old SQL-bound signatures are not automatically the new public API.

## 11. Persistence, concurrency and multi-user growth

LadybugDB with Cypher is the selected backend. This is an informed model/backend change, not an open database vote or driver substitution. Do not retain SQLite for settings, sessions or transcripts by undocumented exception.

Logical JSON and physical storage are separate contracts. Storage may use internal keys, normalized relations, indexes and projections, but must reconstruct the same tree, exact addresses and native arrays without public row IDs or required wrappers. Persist source records and derived ancestry/incidence projections consistently. Export/import must round-trip the logical representation and retain native ordering where present.

**Engineering proposal:** one database-owning service mediates access to each authoritative embedded database. Browser, MCP, CLI and module callers use shared operations rather than independently writing database files. Multiple clients do not require multiple database writers. Database concurrency and throughput must be tested against the selected Ladybug version; serialization alone does not prevent stale-intent overwrites.

The shared service must distinguish caller, selected project and logical agent/context. Permissions are enforced before reads, knowledge retrieval, mutation, event subscriptions and dispatch. Caller-supplied actor/project fields do not authenticate anyone. Attribution, revision checks and retry identity live in service/persistence metadata; they do not become compulsory properties on every functional element.

The existing Node design already describes invited accounts, passkey sign-in, revocation, read/write/dispatch capabilities, owner administration and per-account view focus. It also describes self-hosting, a broker/relay and hosted instances. Preserve these as recovered capabilities to reconcile into the new runtime. The word Node here names a deployment/module, not necessarily Node.js.

That historical document does not prove the new system already supports fine-grained project sharing or tenant isolation. Its SQLite auth store and process-local restart assumptions are not silently adopted into a Ladybug rebuild. Exact project grants and sharing behavior need an explicit access contract, grounded in the existing design rather than an invented role ladder.

Multi-user acceptance requires:

- Two authorized people can use the same project without changing each other's focus, session receipts or private context state.
- A caller cannot select a project, layer, inbox, event stream or dispatch action beyond its granted access.
- Concurrent reads see a consistent revision. Incompatible stale writes report conflicts instead of replacing another contribution.
- A retried operation can be reconciled after disconnect without applying it twice; a database lock is not treated as an edit-merge policy.
- Changes retain attributable provenance; revocation stops subsequent access. Private assessment data remains private.
- Export/move/backup does not leak credentials or require rewriting the functional namespace.

The same functional schema can serve single-user and shared-project deployments. No schema can alone establish authentication, isolation, multi-writer correctness or horizontal scale. Do not claim those properties from a passing JSON test. Horizontal database partitioning/replication is not established by the current Ladybug selection.

## 12. Communication and event delivery

Purposeful messages, assignments, peer questions, handoffs, instructed stops and reasoned events are allowed. Do not implement continual ticket/status/log streaming into an agent harness. The prior failure was context pollution and unnecessary inference cost; it was not event-driven orchestration itself.

The mailbox is deliberately lightweight. A subscribed recipient can receive a short availability notice such as **“1 message waiting”**. Message bodies are retrieved through a known, documented and progressively discoverable mailbox-read capability, or deliberately delivered when a reasoned orchestration action calls for it. The notice does not include message bodies, ticket histories or a mailbox dump. Retrieval is an explicit action, not a recurring check. A count notice alone does not require a model turn; an assignment or other purposeful event can still direct action when appropriate.

Agents and namespace locations can have addressed inboxes. Pending availability, body delivery, acknowledgment and retained history remain distinguishable. Durable semantic memory is not inferred from reading a message. Preserve pending messages after a failed delivery; do not mark them consumed merely because a waiting-count notice reached the transport. The exact read/ack binding can be completed with the mailbox module. A general leasing system, fan-out framework or complex claim protocol is not a prerequisite for the initial mailbox.

### Subscription transport and responsiveness

Use event subscriptions rather than recurring application polling. **The control channel uses WebTransport.** Broad browser compatibility is not required: the owner accepts a selected browser/version or a custom application for this niche system. Validate the intended endpoints and expose connection status. No WebSocket fallback or adapter is included in the planned scope. Do not silently fall back to periodic HTTP/database/mailbox checks.

**Implementation work:** select and document the tested browser/native client and server stack for concurrent agentic/embedded traffic. Keep event meaning and subscription APIs behind the existing module boundary. No particular library/embedded target is claimed to have passed integration or performance tests yet.

WebTransport is usable: [MDN compatibility data](https://github.com/mdn/browser-compat-data/blob/main/api/WebTransport.json) lists core support in Chrome 97, Firefox 114 and Safari 26.4, while individual features still vary. QUIC avoids transport head-of-line blocking between independent streams: loss in one reliable stream need not hold up delivery on another. Ordering/retransmission can still stall that stream, and streams share connection/network resources. Putting all traffic in one reliable stream would discard much of this advantage. Optional unreliable datagrams suit fresh sensor/simulation samples that supersede older samples.

The owner's additional mobile compatibility evidence reinforces this choice. Core API introduction versions are distinct from the specific client versions tested for this product:

| Browser/client family | Core API introduction |
| --- | --- |
| Chrome desktop / Chrome for Android | 97 |
| Firefox desktop / Firefox for Android | 114 |
| Safari macOS / Safari on iOS | 26.4 |
| Samsung Internet for Android | 18; MDN's browser data maps this release to Blink99, after version17's Blink96. |
| Android WebView | Chromium/WebView97 generation onward; confirm availability in the actual embedding application. |

Browser sessions use a secure context and a functioning WebTransport endpoint. Document and test the stream/datagram features actually required; core API presence is not a promise that every optional API has identical support. Broad desktop/mobile availability supports the chosen architecture without introducing a fallback requirement. Native/embedded client support is verified against its own implementation rather than inferred from this browser table.

**Candidate stream mapping:** reliable streams for assignments, mailbox bodies and other operations that must arrive; separate independent reliable traffic such as context transfers from urgent control; datagrams only for data whose explicit semantics permit loss/reordering. Cross-stream causal requirements need application revisions/sequence relationships rather than an assumed global delivery order. This mapping remains engineering work, not a new functional data shape or mandatory tool inventory.

Embedded support is determined by the actual client stack and device budget; generic QUIC support alone does not establish WebTransport session support. Measure target CPU, memory, bytes per event and p50/p95/p99 control latency during bulk traffic, packet loss and slow-consumer conditions. WebTransport can reduce retransmission and application multiplexing costs for suitable workloads, but lower total overhead for every message/device is not assumed. Deployment must support the chosen HTTP/3/QUIC path, and server-library support must be checked separately from browser support.

[Node's current development QUIC documentation](https://github.com/nodejs/node/blob/main/doc/api/quic.md) labels the built-in API early development and states that WebTransport helpers are not implemented. This is not a claim that Node cannot serve WebTransport: [MDN's API guide](https://developer.mozilla.org/en-US/docs/Web/API/WebTransport_API) lists a third-party Node implementation and other server options. Select a supported library/deployment from evidence rather than assuming built-in QUIC is a complete WebTransport server. Reliable assignments, mailbox bodies and commits must not be sent as disposable datagrams. The channel needs bounded queues, access checks and reconnect/recovery behavior.

This control-channel choice does not redefine MCP's wire protocol. The MCP adapter uses transports and event capabilities actually supported by the selected protocol and harness, and bridges the same internal event subscriptions. Do not advertise WebTransport as native MCP support without an applicable binding.

**Engineering proposal:** establish a current snapshot when subscribing and recover missed changes on reconnect using a subscription cursor or revision. Signal publication after the authoritative change commits. Slow consumers get bounded buffering/backpressure; replaceable availability counts can be coalesced without discarding the queued messages or purposeful events they represent. A slow subscriber must not stall unrelated operations. Recovery is explicit reconnection/resynchronization, not a background scan loop.

Keep handlers asynchronous and avoid blocking the event loop with database work, model calls or rendering. Measure queue wait, service time, transport time and client application time separately, including tail latency under concurrent agents/users. Publish those measurements to the operator without logging them into agent context. Responsiveness is a foundation acceptance requirement; no arbitrary millisecond guarantee is claimed before a workload has been measured.

Use the selected draft MCP event binding when the actual harness supports it. Otherwise use a chassis-local event/message with equivalent meaning. Preserve origin, recipient, identity and causation. Do not fabricate user authorship. MCP connectivity alone does not prove event capability.

The owner reported Codex support at discussion time; this is not a permanent vendor allowlist or a test result for every current client. Negotiate/verify actual supported versions. After an unknown send, reconcile identity and outcome before choosing a second path; do not blindly double-send through fallback.

Event production, durable recording, transport receipt, harness delivery and model turn start are separate observable stages. Diagnostics remain inspectable without waking a model on every update.

## 13. Agent identity, lifecycle and orchestration

Workers, the user-facing liaison and the system can launch agents. An instructed agent can stop another without having launched it. Use prompts, procedures and configured restrictions, not a single exclusive orchestration authority or creator-only control. Do not add tool prerequisites based on visiting related functionality.

Orchestration is dynamic and configurable. Solo work, peers, differentiated teams, prompt variants, agent messaging and system-directed assignments are valid patterns. Evaluate refinements using completed outcomes, costs and coordination evidence. Do not mandate a paid reviewer cascade for every task.

A logical agent has unique persistent identity and retained conversation, work, handoff and commit references across execution contexts. Independently proceeding forks receive independent identities. Retirement ends runtime eligibility without erasing historical addressability. Conversation history is not a claim that every source edit appears in chat.

After a task, a useful worker becomes dormant and can accept further work. It becomes ineligible for fresh work when cache timeout makes resending retained context more expensive than orienting a fresh worker. Measure the crossover per model/harness. Do not substitute a universal five-minute rule, score penalty or arbitrary utilization cutoff.

Context-capacity renewal is distinct from cache economics: the recovered policy includes approximately 50% self-handoff intent, graduated warnings and approximately 65% later enforcement under configuration. Preserve useful source/work references without resending all prior context. The old lowest-score/two-cycle retirement proposal is not current default behavior.

## 14. Peer assessment

Only observed active multi-agent participation earns assessment. Teammates observe and assess one another; solo work is unscored, not a zero. Agents can use others' aggregate scores to select partners. Do not present the subject's own score, reviewer identities or individual reviews to that agent. Private attribution can remain in audit storage.

| Criterion | Weight | Rating |
| --- | --- | --- |
| Efficient | 10 | 0–5 |
| Alert & Aware | 20 | 0–5 |
| Thorough | 30 | 0–5 |
| Coordination | 40 | 0–5 |

Assessment percentage is `Σ(weight × rating / 5) + bonus`, with an optional bonus up to 5. Each assessment ranges from 0 through **105%**. Values over 100 are intentional so agents can recover.

Reputation is the arithmetic mean of current qualifying assessment revisions over the retained logical-agent history. Do not clamp at 100, inject a synthetic initial 100, reset on context renewal, or count a replacement review twice. No qualifying assessments means null/unscored. `100, 92, 105, 105` averages to **100.5%**.

Retain rubric version and review revisions. A future differently scaled rubric needs an explicit migration/aggregation policy. Score does not confer exclusive orchestration authority or establish a default retirement rule.

## 15. Coupled work and automatic feature delivery

ICE denotes indivisible functional coupling. Preserve the evidence and coherent contribution when work spans multiple elements. A relationship `ice` boolean is not a complete group representation, nor permission to infer arbitrary connected components as Blocks. Do not split coupled work into incompatible worktrees solely by directory boundaries. Exact persisted Block/group representation remains engineering work; it does not require redesigning provider references.

Completed feature work creates a feature commit automatically in both modes. **Full Auto** integrates/lands, pushes, confirms and cleans worktrees. With Full Auto disabled, committed work is delivered as a pull request. Preserve contribution and coherent work-unit links.

Commit, integration, remote publication, confirmation and cleanup are distinct recoverable phases. Failed/unknown publication must not delete work or cause blind duplicate commits/PRs. Integration conflicts retain the work and explain the next action. Human-readable commit descriptions state the problem, behavioral change and relevant verification.

These are product-mode requirements, not permission to publish this local specification, create a remote repository or run agents with external side effects during review.

## 16. Sensor and control scheme

| Profile | Coverage/data | Range |
| --- | --- | --- |
| Physical camera/depth | Camera view with overlaid depth grid; stated 60° FOV. | Up to 3500 mm. |
| Virtual radial surround | 360° around the agent in eight spherical wedges, with the stated top-to-bottom coverage; queryable at any time. | Full unsigned 16-bit millimeter range, 0–65535 mm, approximately 215 ft. |
| Conventional virtual forward | Standard 60° forward FOV and readable depth array. | Standard 3500 mm profile. |

A virtual trigger identifies the 45° zone and up/down angle. Radial virtual coverage is established; do not reopen sphere-versus-cone as though the owner never explained it. Exact elevation sampling, frame/angle conventions, seams/poles, array indices and quality encoding must be specified without silently reusing a forward 8×8 grid as the surround model.

Code can evaluate the sensor and produce an event through supported MCP binding or chassis fallback. Consumers choose actions. A rear event may lead to a head turn followed by camera/depth retrieval; a stealth NPC may use only the forward profile to constrain sight. These are examples, not mandatory chassis reactions.

Preserve valid uint16 distances, including 32768–65535. Unavailable/no-return encoding must not silently consume a valid distance. High-rate simulation, sensing and reflex behavior remain in responsible modules; the LLM interface does not promise a real-time control latency. Functional namespace location and spatial pose are distinct.

## 17. Browser, shell and operator experience

Browser diagrams and dynamically drawn charts are central presentation capabilities over the same functional map. A generated sparse tree can show element names for the region in focus. Shell diagrams are a useful additional projection, not a replacement model or a requirement to arrange the namespace like the owner's illustrative deployment chart.

Operators get readable commands, help, results and actionable errors. Raw serialized option records belong in an explicit JSON/diagnostic mode. Do not dump internal registries or full schemas as normal command output. CLI and MCP are distinct interfaces over shared services; every CLI command does not become an MCP tool.

Chat shows stable, accessible model and reasoning-effort controls. Preserve choices independently by native option identity, not a category that collides between unrelated options. Do not silently reset effort upward or discard user choices when starting/resuming a session. A “ready” status must not misrepresent actual assignment/delivery/completion evidence.

Per-user focus, saved workspace, session state and receipts must not overwrite another user's state. Diagnostics expose relevant source revisions, transport state, timings, calls/tokens/cost and delivered bytes without live-streaming them into the agent's context.

Provide live operator views for per-agent context usage and the actual exposed tool surface described in sections 8–9. Subscribe to changes instead of refreshing on a timer. Unknown usage is displayed as unknown, not zero; cumulative token billing is not labelled current context. The mailbox presentation can remain as small as “1 message waiting” with a direct way to read it. Detailed diagnostics are available on demand without burdening routine use.

## 18. Composition, lexicalization and improvement

Compose documentation, specifications, explanations and user journeys from a named source/revision cut with dependencies and an output manifest. An OP or specification Objective Purpose change can invalidate dependent output. A rename alone does not establish functional transformation.

Generate a new output cut; on failure retain the prior complete result. Do not claim deterministic arbitrary code regeneration, automatic theory proof or zero drift. A source URI without retained bytes/version does not establish a reproducible frozen source cut.

Lexicalization grounds project referents using project names while preserving the user's requested operation. Keep selected imperatives identifiable. Do not silently substitute an easier task, ontology or programming interpretation.

Blindspot A/B/C reasoning records substantive reason, novelty/relevance, location and how the issue is handled. The categories are not new lifecycle states or a compulsory two-pass pipeline. New observations can inform prompts and procedures without automatically waking every participant.

## 19. Quality and acceptance

Quality means code and contracts the owner can inspect, bounded changes, correct shared behavior and demonstrated failure handling. Preserve intentional design. Do not create massive uncommitted rewrites, unrelated formatting churn, hidden prompt edits or new gates as a substitute for engineering.

The following are required product acceptance scenarios. Except the explicitly reported schema checks, they have **not been demonstrated by this document**.

| ID | Acceptance evidence |
| --- | --- |
| CAP-1 | Intake software/specification, story, photograph and mixed folder with the same functional method; correct names, reverse namespace, CQU pathway and PE tree resolution. |
| CAP-2 | Submit one-receiver commands using wants/goal/function/intent; validate input and the resulting nested map. Test referenced-element rejection with remediation, relationship deletion, orphan query, property removal with update/null, stale writes, retries, and preservation through annealing. |
| CAP-3 | All three views return their defined contents; global retains wants, local knowledge excludes neighbor bodies; deep complete retrieval has no silent cap. |
| CAP-4 | Native layer round-trip, metadata-word branches, inherited scope, omitted/empty selection and branch restore preserve identity and payload. |
| CAP-5 | Progressive native schema/skill discovery without a bulk startup catalog or visit/read prerequisite; active-work skill serving behaves as specified. |
| CAP-6 | Once/version/epoch body delivery, relevant deltas, explicit refresh and honest unknown retention after compaction. |
| CAP-7 | A lightweight waiting-count notice and discoverable explicit message read; no bodies auto-dumped; failed delivery preserves pending work. Detailed claim/ack behavior is completed incrementally with its module. |
| CAP-8 | Worker, liaison and system launch; instructed non-launcher stop; 100 routine ticket/log changes cause zero automatic log-stream injections while a purposeful event remains deliverable. |
| CAP-9 | Evidence-based coupled work stays coherent through worktree/commit handling; no invented exclusive orchestration hierarchy. |
| CAP-10 | Dormancy/reuse and measured cache-cost crossover; persistent history survives renewal and retirement; forks have independent identities. |
| CAP-11 | Observed peer scoring only; solo null; weighted maximum105; example mean100.5; replacement reviews and privacy correct. |
| CAP-12 | Real Ladybug transactions, rollback, restart, export/import, consistent projections, stale conflicts and multi-user isolation/attribution. |
| CAP-13 | Actual supported MCP event binding and chassis fallback preserve origin/identity; validate the WebTransport control channel on a documented selected browser/custom client and intended embedded stack. No WebSocket fallback/adapter is in scope. Measure CPU/memory/bytes and control-tail latency under concurrent streams, loss and slow consumers. Idle traces show no recurring application polling. Reconnection recovers missed changes; unknown send does not blind-send twice. |
| CAP-14 | Physical and virtual profiles; 45° trigger/elevation;3500/3501/32767/32768/65535mm without clipping or signed wrap; consumer chooses action. |
| CAP-15 | Composition from a named source cut; dependency invalidation and failed-generation recovery preserve a complete prior output. |
| CAP-16 | Per-agent current context/capacity with reported-versus-estimated status, separate cumulative usage/cost, and actual exposed tools/schema footprint. Monitoring does not load context into the inspected agent or poll it. Measure queue/service/transport/client tail latency under concurrent load; no diagnostic flood into the harness. |
| CAP-17 | Core without feature modules; module contract/template/public DAO parity; clean async lifecycle; usable CLI and stable model/effort controls. |
| CAP-18 | Historical mandatory Python–Node channel is superseded. This identifier is retained for traceability and is not reused for a new requirement. |
| CAP-19 | Feature commit in both modes; Full Auto land/push/confirm/cleanup; other mode PR; failure and unknown publication retain work. |
| CAP-20 | Configurable solo/peer/team procedures compared using outcome/cost evidence without compulsory reviewer cascades. |

Tests of schema shape do not prove intake semantics, protocol interoperability, authorization, concurrency, a working runtime or production readiness. Tests must exercise actual behavioral risks, including failure/restart, rather than just echo implementation details. Do not certify the design solely from assistant-authored fixtures.

## 20. Implementation sequence and remaining engineering decisions

This sequence is an engineering recommendation. It delivers usable slices without turning every task into a new permission gate.

1. Review this single specification and its concrete examples. Confirm material proposals; retain the owner's corrections in an append-only decision record. Do not restart the requirements interview.
2. Select the runtime with a small evidence-based comparison: module lifecycle/shared services, Ladybug binding, MCP SDK/harness support, ACP integration, packaging and owner maintainability. Multi-user growth is a contract requirement in every option, not a language benchmark assumption.
3. Establish the independent chassis, public service/DAO contract, Ladybug owner and event subscription boundary. Demonstrate transaction rollback/restart, two-client stale-conflict behavior, no recurring application polling and responsive independent subscribers before claiming foundation readiness.
4. Implement project/caller identity propagation and permission checks alongside persistence. Local mode can bind a known local principal; it must not bake a global anonymous user into module APIs.
5. Deliver native namespace read/write/export and the three views. Test the corrected representation against real artifacts and retained owner examples. Repair mechanics without silently changing authored intake semantics.
6. Deliver the MCP functional surface and progressive skill/context behavior as a working standalone slice, with per-agent context and actual tool-surface monitoring. Verify actual clients and supported event capabilities. A lightweight mailbox can begin with availability notice and explicit read; complete its detailed binding incrementally rather than blocking this slice on a larger messaging framework.
7. Deliver browser/shell projection, dispatch/ACP, messaging and event fallback, lifecycle/scoring, then automatic feature completion. Add sensors/composition through modules without changing core independence.

Concrete remaining engineering work: runtime/deployment choice; public module/service signatures; Ladybug physical mapping/version and migration; project-sharing/access policy; remaining command semantics, array updates, conflicts and retry binding; active-work and receipt binding; lightweight mailbox read/ack binding as it is built; supported draft event wire binding and the WebTransport deployment stack; usage adapters and measured latency budgets; ICE group persistence; sensor coordinates/payload; and complete discoverable module tool bindings. These can be completed incrementally in the relevant slices; they are not a demand to predesign a large messaging framework.

These are not requests for the owner to redescribe the functional architecture or write JSON Schema. They are implementation contracts to propose and demonstrate. This document does not reclassify the settled provider layout, metadata ownership, radial coverage, scoring mean or Ladybug selection as open questions.

## 21. Source and correction register

Source paths below are retained local evidence. Historical wording is not a competing current contract.

| Source | Use and precedence |
| --- | --- |
| Owner conversation and JSON examples | Primary decisions and corrections; especially receiving/provider perspectives, provider key layout, native layers, names, universal scope, events, scoring and latest runtime clarification. |
| [Inference Metaform preprint](<../reference/theory/preprint.md>) | Functional theory, unloaded Function/Encounter, relational identity. Historical serialization is not reinstated. |
| [Technical reference](<../reference/theory/technical-reference.md>) | Detailed theoretical definitions and examples, interpreted with later owner corrections. |
| [Canonical intake](<../reference/intake/Canonical_Intake.xml>) and [module intake](<../reference/intake/intake.xml>) | Authored method and historical implementation variants; known later modifications mean neither is declared pristine merely because it exists. |
| [Core axioms](<../reference/intake/metaform_core.axiom>) | Receiving ownership and namespace/name-length semantics. |
| [Existing Node guide](<../reference/architecture/metaform-node.md>) | Accounts, invitation/revocation, capability separation, per-account focus and deployment capabilities. Its backend/security implementation details are not silently ported. |
| Corrected spec/source archive, 2026-10-29 | Functional candidate, preserved originals and provenance. Its version label is v0.4 candidate, not verified recovered v0.9. |
| Interface Schemas, CEL Data Contracts & Backend Specification; SPEC-METAFORM-MCP-BUILD-3.0 | Critiqued Gemini proposals. Their code is not proof of design or working implementation. |
| Latest owner-pasted schema | Structural starting point for this authorized correction; contains documented contradictions with confirmed decisions. |
| Old branches and landed repository review | Capability/rubric/history evidence. No automatic old implementation reuse or claim its tests ran here. |

The 31 October owner discussion and [the supplied query note](docs/mcp-query-source.md) establish the current field names, command input, source URI, and delete/remediation examples. The note preserves the supplied bytes; corrected executable examples are in [tool-examples.json](tool-examples.json) and [intake-example.json](intake-example.json). The current prompt and diagram are [Intake.xml](Intake.xml) and [intake.mmd](intake.mmd). The owner's latest instruction replaces the earlier separate-viewing-tool proposal with one tool. Historical sources below retain their original wording.

Corrections made explicit in this candidate:

| Previous error | Current treatment |
| --- | --- |
| Flat provider addresses treated as owned element objects or a chain | References point to actual elements in the shared nested tree; RE/PE remain perspectives. |
| Provider object map instead of confirmed plural-array layer | `wants[]` contains address-keyed relationship objects. |
| Provider-node copy, generic layers/properties wrapper, invented IDs | Not introduced; relationship has goal/function/intent and optional ice. |
| Functional relationships claimed to be outside knowledge layers | Providers is the functional knowledge layer. |
| Reverse address computed into name | Preserve project name; name_length selects industry-name segments separately. |
| Scalar goal/function on nodes, including root bypass | Relationship fields only; same node rules apply at root and recursively. |
| not_built/missing/todo or BKN | `un_built` for unbuilt intent; separate evidence-based defect review. |
| ICE description copied from IFD | Correct boolean meaning; no invented group ID. |
| Empty goal/function accepted | Nonblank required relationship strings. |
| Schema thought to prove PE resolution/uniqueness or language | Separate cross-reference validation; semantic/language review remains distinct. |
| Unconditional Python-only or mandatory Python–Node bridge | Runtime is a visible technical choice for review; architecture and deliverable continue independently. |
| Single-user assumptions hidden in services | Caller/project/session separation, access enforcement and multi-user conflict evidence are explicit foundation requirements. |

## 22. Appendices and verification

Appendix A contains the current stored-document schema. Appendix B contains the separate tool input schemas. Appendix C contains the agent skill. Appendix D states the scope of local checks. These artifacts do not implement a server.

## Appendix A — stored-document schema

Machine-readable file: [metaform.schema.json](metaform.schema.json). Validate a selected project object, such as `document["mashtrac"]` in the host example. Cross-reference checks run separately.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Metaform Graph Model",
  "description": "The JSON object is the functional namespace. Elements occupy nested paths. Each element owns its properties and native knowledge arrays. wants[] holds receiver-owned relationships keyed by project-relative provider address. Each provider also exists at its own nested path. Tool command addresses do not replace this stored tree.",
  "type": "object",
  "$defs": {
    "NamespaceValue": {
      "title": "Value at a namespace address",
      "description": "Objects extend the addressed hierarchy or hold structured data. Arrays denote composed element layers; scalars are direct values.",
      "oneOf": [
        {
          "$ref": "#/$defs/NamespaceNode"
        },
        {
          "$ref": "#/$defs/ComposedElementLayer"
        },
        {
          "type": [
            "string",
            "number",
            "boolean",
            "null"
          ]
        }
      ]
    },
    "NamespaceNode": {
      "title": "Namespace branch or receiving element",
      "description": "Namespace branch or receiving element. Its properties and layers are directly on the element. The same word can name metadata or a namespace branch according to its value and context.",
      "type": "object",
      "properties": {
        "name": {
          "anyOf": [
            {
              "type": "string",
              "description": "The name used for this functionality in project documentation or specifications, such as Metaform.",
              "minLength": 1,
              "pattern": "\\S"
            },
            {
              "$ref": "#/$defs/NamespaceNode"
            },
            {
              "$ref": "#/$defs/ComposedElementLayer"
            }
          ]
        },
        "role": {
          "anyOf": [
            {
              "type": "string",
              "description": "Systemic role: Definitive (the element whose loss means the artifact can no longer remain what it is), Supportive (an indivisibly coupled element meant to assist the Definitive element), Notable (a discrete, structurally independent feature or specialized exception with unique systemic significance) or Divergent (an unaligned, weak or redundant element to be realigned or ejected)."
            },
            {
              "$ref": "#/$defs/NamespaceNode"
            },
            {
              "$ref": "#/$defs/ComposedElementLayer"
            }
          ]
        },
        "status": {
          "anyOf": [
            {
              "type": "string",
              "description": "Implementation state. Use un_built for intended functionality not yet built. Legacy missing/todo spellings and intake BKN/broken judgments are not accepted. Other lifecycle state names are not defined by this schema.",
              "minLength": 1,
              "pattern": "\\S",
              "not": {
                "enum": [
                  "missing",
                  "MISSING",
                  "BKN",
                  "broken",
                  "todo",
                  "TODO"
                ]
              }
            },
            {
              "$ref": "#/$defs/NamespaceNode"
            },
            {
              "$ref": "#/$defs/ComposedElementLayer"
            }
          ]
        },
        "technical_name": {
          "anyOf": [
            {
              "type": "string",
              "description": "The well-understood practitioner short name derived from the leaf segments. Must exactly match the same number of leading words of the reversed, space-separated namespace address, and must not match `name`.",
              "minLength": 1,
              "pattern": "\\S"
            },
            {
              "$ref": "#/$defs/NamespaceNode"
            },
            {
              "$ref": "#/$defs/ComposedElementLayer"
            }
          ]
        },
        "wants": {
          "anyOf": [
            {
              "$ref": "#/$defs/Wants"
            },
            {
              "$ref": "#/$defs/NamespaceNode"
            }
          ],
          "description": "An array is the functional knowledge layer. An object is a namespace branch and follows namespace rules."
        },
        "why": {
          "anyOf": [
            {
              "$ref": "#/$defs/NamespaceNode"
            },
            {
              "$ref": "#/$defs/ComposedElementLayer"
            }
          ],
          "description": "This word may name a namespace branch or native layer. Scalar relationship fields belong inside wants, not on the element."
        },
        "how": {
          "anyOf": [
            {
              "$ref": "#/$defs/NamespaceNode"
            },
            {
              "$ref": "#/$defs/ComposedElementLayer"
            }
          ],
          "description": "This word may name a namespace branch or native layer. Scalar relationship fields belong inside wants, not on the element."
        },
        "project": {
          "anyOf": [
            {
              "type": "string",
              "minLength": 1,
              "pattern": "\\S",
              "description": "Optional project metadata; does not introduce a required wrapper."
            },
            {
              "$ref": "#/$defs/NamespaceNode"
            },
            {
              "$ref": "#/$defs/ComposedElementLayer"
            }
          ]
        },
        "uri": {
          "anyOf": [
            {
              "type": "string",
              "minLength": 1,
              "pattern": "\\S",
              "description": "One source link to the entry point for this functionality. A relative file path is allowed."
            },
            {
              "$ref": "#/$defs/NamespaceNode"
            }
          ]
        },
        "providers": {
          "$ref": "#/$defs/NamespaceNode",
          "description": "This word may name a namespace branch. The functional relationship array is wants, not providers."
        },
        "op": {
          "anyOf": [
            {
              "$ref": "#/$defs/NamespaceNode"
            },
            {
              "$ref": "#/$defs/ComposedElementLayer"
            }
          ],
          "description": "This word may name a namespace branch or native layer. Scalar relationship fields belong inside wants, not on the element."
        },
        "ef": {
          "anyOf": [
            {
              "$ref": "#/$defs/NamespaceNode"
            },
            {
              "$ref": "#/$defs/ComposedElementLayer"
            }
          ],
          "description": "This word may name a namespace branch or native layer. Scalar relationship fields belong inside wants, not on the element."
        },
        "direction": {
          "anyOf": [
            {
              "$ref": "#/$defs/NamespaceNode"
            },
            {
              "$ref": "#/$defs/ComposedElementLayer"
            }
          ],
          "description": "This word may name a namespace branch or native layer. Scalar relationship fields belong inside wants, not on the element."
        },
        "ifd": {
          "anyOf": [
            {
              "$ref": "#/$defs/NamespaceNode"
            },
            {
              "$ref": "#/$defs/ComposedElementLayer"
            }
          ],
          "description": "This word may name a namespace branch or native layer. Scalar relationship fields belong inside wants, not on the element."
        }
      },
      "additionalProperties": {
        "$ref": "#/$defs/NamespaceValue"
      },
      "propertyNames": {
        "pattern": "^[^.$\\[\\]\\s]+$",
        "description": "One namespace segment, never a dotted reference or JSONPath expression."
      }
    },
    "ComposedElementLayer": {
      "title": "Array-valued composed element layer",
      "description": "An array at a plural-named namespace location is a knowledge layer. Its members retain their native formats and nesting. Do not reinterpret fields inside native members as functional namespace branches.",
      "type": "array",
      "items": true
    },
    "Wants": {
      "title": "Functional knowledge layer",
      "type": "object",
      "description": "Relationships owned by this receiver, keyed by the provider's address: one relationship per provider. Each key refers to the actual provider in the nested tree. The provider keeps its properties and knowledge at its own location.",
      "propertyNames": {
        "pattern": "^[^.$\\[\\]\\s]+(?:\\.[^.$\\[\\]\\s]+)*$",
        "description": "Project-relative reference to an element in the actual nested namespace."
      },
      "additionalProperties": {
        "$ref": "#/$defs/WantRecord"
      }
    },
    "WantRecord": {
      "title": "Want record",
      "description": "Why this receiver wants this provider, what the provider supplies for that goal, and what the receiver plans to do with the substance. Keep one relationship per provider address within a receiver.",
      "type": "object",
      "properties": {
        "direction": {
          "type": "string",
          "description": "The direction of the substantial flow of information which satisfies the (OP) goal, relative to the receiver, not including the request: outbound from the receiver, inbound to the receiver, or two-way.",
          "enum": [
            "outbound",
            "inbound",
            "two-way"
          ]
        },
        "why": {
          "type": "string",
          "description": "What this receiver seeks to accomplish through this provider. This is its Operative Purpose (OP). Use clear, simple technical English.",
          "minLength": 1,
          "pattern": "\\S"
        },
        "how": {
          "type": "string",
          "description": "How this provider serves this receiver's goal in this encounter. This is its Encounter Function (EF). Use clear, simple technical English.",
          "minLength": 1,
          "pattern": "\\S"
        }
      },
      "required": [
        "direction",
        "why",
        "how"
      ],
      "additionalProperties": false
    }
  },
  "$comment": "Owner-authorized terminology and tool-contract update, 2026-10-31. This schema validates one selected project namespace. A host may store it below a project key. Provider addresses resolve from that selected project, not from the host root. validate_metaform.py also checks reference resolution, duplicate relationships and name_length bounds. MCP command input has a separate schema. Validation does not prove functional reasoning. CQU and the authored concepts remain in force.",
  "$ref": "#/$defs/NamespaceNode"
}
```

## Appendix B — single MCP tool contract

Machine-readable file: [mcp-tools.proposed.json](mcp-tools.proposed.json). It declares one tool for changes and reads. The name remains provisional. Working command input follows section 7. Shared definitions below refer to Appendix A's file; the registry embeds them so a client need not fetch a local file. Response examples are in [tool-examples.json](tool-examples.json); a complete mutation success envelope has not been selected.

### project-map

```json
{
  "name": "project-map",
  "description": "Use this single Metaform tool for add, update, delete, orphaned, goto, map, raw dumps and addressed reads. Work on one receiving element at a time. Input addresses select actual elements in the nested namespace. wants records refer to providers at their own locations. Tool name is provisional.",
  "inputSchema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "description": "One operation on one receiving address, an orphan query, a goto, the map, a raw dump, or an addressed read. A key without a period is a command; a key with a period reads. The selected project comes from caller context. Addresses in commands are selectors; storage remains a nested namespace. Validate this input before any mutation.",
    "oneOf": [
      {
        "type": "object",
        "properties": {
          "add": {
            "type": "object",
            "minProperties": 1,
            "maxProperties": 1,
            "propertyNames": {
              "pattern": "^(?:\\.|[^.$\\[\\]\\s]+(?:\\.[^.$\\[\\]\\s]+)*)$"
            },
            "additionalProperties": {
              "$ref": "#/$defs/AddFields"
            }
          }
        },
        "required": [
          "add"
        ],
        "additionalProperties": false
      },
      {
        "type": "object",
        "properties": {
          "update": {
            "type": "object",
            "minProperties": 1,
            "maxProperties": 1,
            "propertyNames": {
              "pattern": "^(?:\\.|[^.$\\[\\]\\s]+(?:\\.[^.$\\[\\]\\s]+)*)$"
            },
            "additionalProperties": {
              "$ref": "#/$defs/UpdateFields"
            }
          }
        },
        "required": [
          "update"
        ],
        "additionalProperties": false
      },
      {
        "type": "object",
        "properties": {
          "delete": {
            "type": "object",
            "minProperties": 1,
            "maxProperties": 1,
            "propertyNames": {
              "pattern": "^[^.$\\[\\]\\s]+(?:\\.[^.$\\[\\]\\s]+)*$"
            },
            "additionalProperties": {
              "oneOf": [
                {
                  "$ref": "#/$defs/Empty"
                },
                {
                  "$ref": "#/$defs/DeleteWants"
                }
              ]
            }
          }
        },
        "required": [
          "delete"
        ],
        "additionalProperties": false
      },
      {
        "type": "object",
        "properties": {
          "orphaned": {
            "$ref": "#/$defs/Empty"
          }
        },
        "required": [
          "orphaned"
        ],
        "additionalProperties": false
      },
      {
        "type": "object",
        "description": "goto places the agent at an address and returns its summary sheet: the element and its wants, what relies on it, layer record counts, skill frontmatter and the memory count. A later goto to the same address in the same context returns only what changed (metaform/SPEC.md R-5.30).",
        "properties": {
          "goto": {
            "type": "string",
            "pattern": "^(?:\\.|[^.$\\[\\]\\s]+(?:\\.[^.$\\[\\]\\s]+)*)$"
          }
        },
        "required": [
          "goto"
        ],
        "additionalProperties": false
      },
      {
        "type": "object",
        "description": "map returns the shallow graph: every element address, each want as an edge from the element that holds it to the element it names, and the one Definitive element. No fields and no layers (metaform/SPEC.md R-5.11).",
        "properties": {
          "map": {
            "$ref": "#/$defs/Empty"
          }
        },
        "required": [
          "map"
        ],
        "additionalProperties": false
      },
      {
        "type": "object",
        "description": "A key that starts with a period is a raw dump: the stored nested JSON at that path, which is the JSON path $.<project> with $.<project> left off. \".\" dumps the whole project; \".code.server\" dumps that element and everything beneath it. Every layer is included (metaform/SPEC.md R-5.34).",
        "minProperties": 1,
        "maxProperties": 1,
        "propertyNames": {
          "pattern": "^\\.(?:[^.$\\[\\]\\s]+(?:\\.[^.$\\[\\]\\s]+)*)?$"
        },
        "additionalProperties": {
          "$ref": "#/$defs/Empty"
        }
      },
      {
        "type": "object",
        "minProperties": 1,
        "maxProperties": 1,
        "propertyNames": {
          "pattern": "^(?!(?:add|update|delete|orphaned|goto|map)$)[^.$\\[\\]\\s]+(?:\\.[^.$\\[\\]\\s]+)*$"
        },
        "additionalProperties": {
          "$ref": "#/$defs/LayerRead"
        },
        "description": "An addressed read: the element's own fields, plus each layer named with {} as its value (metaform/SPEC.md R-5.10, R-6.27)."
      }
    ],
    "$defs": {
      "NamespaceValue": {
        "title": "Value at a namespace address",
        "description": "Objects extend the addressed hierarchy or hold structured data. Arrays denote composed element layers; scalars are direct values.",
        "oneOf": [
          {
            "$ref": "#/$defs/NamespaceNode"
          },
          {
            "$ref": "#/$defs/ComposedElementLayer"
          },
          {
            "type": [
              "string",
              "number",
              "boolean",
              "null"
            ]
          }
        ]
      },
      "NamespaceNode": {
        "title": "Namespace branch or receiving element",
        "description": "Namespace branch or receiving element. Its properties and layers are directly on the element. The same word can name metadata or a namespace branch according to its value and context.",
        "type": "object",
        "properties": {
          "name": {
            "anyOf": [
              {
                "type": "string",
                "description": "The name used for this functionality in project documentation or specifications, such as Metaform.",
                "minLength": 1,
                "pattern": "\\S"
              },
              {
                "$ref": "#/$defs/NamespaceNode"
              },
              {
                "$ref": "#/$defs/ComposedElementLayer"
              }
            ]
          },
          "role": {
            "anyOf": [
              {
                "type": "string",
                "description": "Systemic role: Definitive (the element whose loss means the artifact can no longer remain what it is), Supportive (an indivisibly coupled element meant to assist the Definitive element), Notable (a discrete, structurally independent feature or specialized exception with unique systemic significance) or Divergent (an unaligned, weak or redundant element to be realigned or ejected)."
              },
              {
                "$ref": "#/$defs/NamespaceNode"
              },
              {
                "$ref": "#/$defs/ComposedElementLayer"
              }
            ]
          },
          "status": {
            "anyOf": [
              {
                "type": "string",
                "description": "Implementation state. Use un_built for intended functionality not yet built. Legacy missing/todo spellings and intake BKN/broken judgments are not accepted. Other lifecycle state names are not defined by this schema.",
                "minLength": 1,
                "pattern": "\\S",
                "not": {
                  "enum": [
                    "missing",
                    "MISSING",
                    "BKN",
                    "broken",
                    "todo",
                    "TODO"
                  ]
                }
              },
              {
                "$ref": "#/$defs/NamespaceNode"
              },
              {
                "$ref": "#/$defs/ComposedElementLayer"
              }
            ]
          },
          "technical_name": {
            "anyOf": [
              {
                "type": "string",
                "description": "The well-understood practitioner short name derived from the leaf segments. Must exactly match the same number of leading words of the reversed, space-separated namespace address, and must not match `name`.",
                "minLength": 1,
                "pattern": "\\S"
              },
              {
                "$ref": "#/$defs/NamespaceNode"
              },
              {
                "$ref": "#/$defs/ComposedElementLayer"
              }
            ]
          },
          "wants": {
            "anyOf": [
              {
                "$ref": "#/$defs/Wants"
              },
              {
                "$ref": "#/$defs/NamespaceNode"
              }
            ],
            "description": "An array is the functional knowledge layer. An object is a namespace branch and follows namespace rules."
          },
          "why": {
            "anyOf": [
              {
                "$ref": "#/$defs/NamespaceNode"
              },
              {
                "$ref": "#/$defs/ComposedElementLayer"
              }
            ],
            "description": "This word may name a namespace branch or native layer. Scalar relationship fields belong inside wants, not on the element."
          },
          "how": {
            "anyOf": [
              {
                "$ref": "#/$defs/NamespaceNode"
              },
              {
                "$ref": "#/$defs/ComposedElementLayer"
              }
            ],
            "description": "This word may name a namespace branch or native layer. Scalar relationship fields belong inside wants, not on the element."
          },
          "project": {
            "anyOf": [
              {
                "type": "string",
                "minLength": 1,
                "pattern": "\\S",
                "description": "Optional project metadata; does not introduce a required wrapper."
              },
              {
                "$ref": "#/$defs/NamespaceNode"
              },
              {
                "$ref": "#/$defs/ComposedElementLayer"
              }
            ]
          },
          "uri": {
            "anyOf": [
              {
                "type": "string",
                "minLength": 1,
                "pattern": "\\S",
                "description": "One source link to the entry point for this functionality. A relative file path is allowed."
              },
              {
                "$ref": "#/$defs/NamespaceNode"
              }
            ]
          },
          "providers": {
            "$ref": "#/$defs/NamespaceNode",
            "description": "This word may name a namespace branch. The functional relationship array is wants, not providers."
          },
          "op": {
            "anyOf": [
              {
                "$ref": "#/$defs/NamespaceNode"
              },
              {
                "$ref": "#/$defs/ComposedElementLayer"
              }
            ],
            "description": "This word may name a namespace branch or native layer. Scalar relationship fields belong inside wants, not on the element."
          },
          "ef": {
            "anyOf": [
              {
                "$ref": "#/$defs/NamespaceNode"
              },
              {
                "$ref": "#/$defs/ComposedElementLayer"
              }
            ],
            "description": "This word may name a namespace branch or native layer. Scalar relationship fields belong inside wants, not on the element."
          },
          "direction": {
            "anyOf": [
              {
                "$ref": "#/$defs/NamespaceNode"
              },
              {
                "$ref": "#/$defs/ComposedElementLayer"
              }
            ],
            "description": "This word may name a namespace branch or native layer. Scalar relationship fields belong inside wants, not on the element."
          },
          "ifd": {
            "anyOf": [
              {
                "$ref": "#/$defs/NamespaceNode"
              },
              {
                "$ref": "#/$defs/ComposedElementLayer"
              }
            ],
            "description": "This word may name a namespace branch or native layer. Scalar relationship fields belong inside wants, not on the element."
          }
        },
        "additionalProperties": {
          "$ref": "#/$defs/NamespaceValue"
        },
        "propertyNames": {
          "pattern": "^[^.$\\[\\]\\s]+$",
          "description": "One namespace segment, never a dotted reference or JSONPath expression."
        }
      },
      "ComposedElementLayer": {
        "title": "Array-valued composed element layer",
        "description": "An array at a plural-named namespace location is a knowledge layer. Its members retain their native formats and nesting. Do not reinterpret fields inside native members as functional namespace branches.",
        "type": "array",
        "items": true
      },
      "Wants": {
        "title": "Functional knowledge layer",
        "type": "object",
        "description": "Relationships owned by this receiver, keyed by the provider's address: one relationship per provider. Each key refers to the actual provider in the nested tree. The provider keeps its properties and knowledge at its own location.",
        "propertyNames": {
          "pattern": "^[^.$\\[\\]\\s]+(?:\\.[^.$\\[\\]\\s]+)*$",
          "description": "Project-relative reference to an element in the actual nested namespace."
        },
        "additionalProperties": {
          "$ref": "#/$defs/WantRecord"
        }
      },
      "WantRecord": {
        "title": "Want record",
        "description": "Why this receiver wants this provider, what the provider supplies for that goal, and what the receiver plans to do with the substance. Keep one relationship per provider address within a receiver.",
        "type": "object",
        "properties": {
          "direction": {
            "type": "string",
            "description": "The direction of the substantial flow of information which satisfies the (OP) goal, relative to the receiver, not including the request: outbound from the receiver, inbound to the receiver, or two-way.",
            "enum": [
              "outbound",
              "inbound",
              "two-way"
            ]
          },
          "why": {
            "type": "string",
            "description": "What this receiver seeks to accomplish through this provider. This is its Operative Purpose (OP). Use clear, simple technical English.",
            "minLength": 1,
            "pattern": "\\S"
          },
          "how": {
            "type": "string",
            "description": "How this provider serves this receiver's goal in this encounter. This is its Encounter Function (EF). Use clear, simple technical English.",
            "minLength": 1,
            "pattern": "\\S"
          }
        },
        "required": [
          "direction",
          "why",
          "how"
        ],
        "additionalProperties": false
      },
      "Empty": {
        "type": "object",
        "maxProperties": 0
      },
      "LayerRead": {
        "type": "object",
        "description": "Name each layer to read at the address where it is written, with {} as its value, such as {\"wants\": {}} or {\"specification\": {}}. An empty object reads only the element's own fields.",
        "propertyNames": {
          "pattern": "^[^.$\\[\\]\\s]+$",
          "description": "One layer name: one namespace segment."
        },
        "additionalProperties": {
          "$ref": "#/$defs/Empty"
        }
      },
      "AddFields": {
        "allOf": [
          {
            "$ref": "#/$defs/NamespaceNode"
          }
        ],
        "type": "object",
        "minProperties": 1,
        "properties": {
          "wants": {
            "$ref": "#/$defs/Wants"
          }
        },
        "description": "Fields supplied for one receiving element. Command addresses select actual nested elements."
      },
      "WantUpdate": {
        "type": "object",
        "minProperties": 1,
        "properties": {
          "direction": {
            "$ref": "#/$defs/WantRecord/properties/direction"
          },
          "why": {
            "$ref": "#/$defs/WantRecord/properties/why"
          },
          "how": {
            "$ref": "#/$defs/WantRecord/properties/how"
          }
        },
        "additionalProperties": false,
        "description": "Supplied fields change one want. Validate the complete resulting want before storing it."
      },
      "WantsUpdate": {
        "title": "Functional knowledge layer",
        "type": "object",
        "description": "Relationships owned by this receiver, keyed by the provider's address: one relationship per provider. Each key refers to the actual provider in the nested tree. The provider keeps its properties and knowledge at its own location.",
        "propertyNames": {
          "pattern": "^[^.$\\[\\]\\s]+(?:\\.[^.$\\[\\]\\s]+)*$",
          "description": "Project-relative reference to an element in the actual nested namespace."
        },
        "additionalProperties": {
          "$ref": "#/$defs/WantUpdate"
        }
      },
      "UpdateFields": {
        "type": "object",
        "minProperties": 1,
        "propertyNames": {
          "pattern": "^[^.$\\[\\]\\s]+$",
          "description": "One namespace segment, never a dotted reference or JSONPath expression."
        },
        "properties": {
          "name": {
            "anyOf": [
              {
                "$ref": "#/$defs/NamespaceNode/properties/name"
              },
              {
                "type": "null"
              }
            ]
          },
          "role": {
            "anyOf": [
              {
                "$ref": "#/$defs/NamespaceNode/properties/role"
              },
              {
                "type": "null"
              }
            ]
          },
          "status": {
            "anyOf": [
              {
                "$ref": "#/$defs/NamespaceNode/properties/status"
              },
              {
                "type": "null"
              }
            ]
          },
          "technical_name": {
            "anyOf": [
              {
                "$ref": "#/$defs/NamespaceNode/properties/technical_name"
              },
              {
                "type": "null"
              }
            ]
          },
          "wants": {
            "$ref": "#/$defs/WantsUpdate"
          },
          "why": {
            "anyOf": [
              {
                "$ref": "#/$defs/NamespaceNode/properties/why"
              },
              {
                "type": "null"
              }
            ]
          },
          "how": {
            "anyOf": [
              {
                "$ref": "#/$defs/NamespaceNode/properties/how"
              },
              {
                "type": "null"
              }
            ]
          },
          "project": {
            "anyOf": [
              {
                "$ref": "#/$defs/NamespaceNode/properties/project"
              },
              {
                "type": "null"
              }
            ]
          },
          "uri": {
            "anyOf": [
              {
                "$ref": "#/$defs/NamespaceNode/properties/uri"
              },
              {
                "type": "null"
              }
            ]
          },
          "providers": {
            "anyOf": [
              {
                "$ref": "#/$defs/NamespaceNode/properties/providers"
              },
              {
                "type": "null"
              }
            ]
          },
          "op": {
            "anyOf": [
              {
                "$ref": "#/$defs/NamespaceNode/properties/op"
              },
              {
                "type": "null"
              }
            ]
          },
          "ef": {
            "anyOf": [
              {
                "$ref": "#/$defs/NamespaceNode/properties/ef"
              },
              {
                "type": "null"
              }
            ]
          },
          "direction": {
            "anyOf": [
              {
                "$ref": "#/$defs/NamespaceNode/properties/direction"
              },
              {
                "type": "null"
              }
            ]
          },
          "ifd": {
            "anyOf": [
              {
                "$ref": "#/$defs/NamespaceNode/properties/ifd"
              },
              {
                "type": "null"
              }
            ]
          }
        },
        "additionalProperties": {
          "$ref": "#/$defs/NamespaceValue"
        },
        "description": "Update supplied fields on one receiving element. Null removes a property; omission leaves it unchanged. Delete individual wants with delete."
      },
      "DeleteWants": {
        "type": "object",
        "properties": {
          "wants": {
            "type": "array",
            "minItems": 1,
            "uniqueItems": true,
            "items": {
              "type": "string",
              "pattern": "^[^.$\\[\\]\\s]+(?:\\.[^.$\\[\\]\\s]+)*$"
            }
          }
        },
        "required": [
          "wants"
        ],
        "additionalProperties": false
      }
    }
  }
}
```

## Appendix C — agent-facing skill

File: [SKILL.proposed.md](SKILL.proposed.md).

```markdown
---
name: metaform
description: Read the functional namespace, use the knowledge needed for the current work, and record findings at the receiving element.
---

# Work with Metaform

The stored JSON tree is the functional namespace. Read addresses backward. `name` is the project's own name. `name_length` counts the trailing segments used for the industry short name. RE and PE are perspectives on the same element.

Work on one receiving element at a time. The single tool is named `project-map`; it handles reads as well as changes. Its input selects an operation and an address; it does not define storage layout. Use `add` or `update` with the receiving address as the key and the supplied fields as its value. Do not add a `data`, `properties`, or `layers` wrapper.

Reason with the authored RE, PE, OP, EF, IFD, CQU, and other concepts. Record the PE's namespace address in the RE's `wants[]`, OP as `goal`, the encounter-specific EF as `function`, and IFD as `direction`. Field names do not replace the definitions or change the method.

`wants[]` is the receiver's functional knowledge layer. Each member maps a provider address to a want record. `goal` states what the receiver seeks to accomplish. `function` states how the provider serves that goal in this encounter. `direction` states the direction of the substantial flow of information which satisfies the (OP) goal, relative to the receiver, not including the request: `outbound`, `inbound`, or `two-way`. Optional `ice` records indivisible coupling. CQU and the other authored concepts retain their meanings.

Every provider also exists at its own nested namespace location. Its properties, knowledge, and own wants live there. Do not copy them beneath a reference. Keep one want per provider address within a receiver. Set one source `uri` on the actual element, pointing to the entry point for its functionality. Keep extra evidence references with the findings that need them.

Read one element with `{"code.masher.widget":{}}`. Delete a want with `{"delete":{"code.protocol.network.tracker.cs":{"wants":["code.masher.widget"]}}}`. Delete an element with `{"delete":{"code.masher.widget":{}}}`. A referenced element cannot be deleted. Inspect returned remediation before submitting it; the error does not authorize automatic deletion of other records.

Use `{"orphaned":{}}` to find unreferenced elements. Do not treat that result as an instruction to delete them. Remove a property with `update` and `null`, for example `{"update":{"code.masher.widget":{"role":null}}}`. Omitted fields remain unchanged. Input validation and validation of the resulting map are separate checks. Do not repeat a write with an unknown outcome until it has been reconciled.

Read-only projections are `local_functional`, `global_functional`, and `local_knowledge`. They do not require a separate viewing tool. Use the single tool for addressed reads; a URI may identify a generated projection. Local functional views include direct wants and incoming receivers. Local knowledge adds knowledge on the focus, without neighbors' knowledge bodies. Global views retain wants but exclude ancillary knowledge bodies. A global read is not required at startup. A URI can also identify a generated view, such as a sparse tree of element names.

Native plural arrays such as `skills[]`, `memories[]`, `tasks[]`, and `inbox[]` retain their contents. Do not invent record IDs or rewrite native skill frontmatter. Record intended functionality not yet built with `status: "un_built"`. Intake records functional intent and separate investigation findings. It does not label unfamiliar intent broken.

Use clear, simple technical English for the recorded goal and function fields. Use the same term for the same thing. Keep the authored intake concepts, exclusions, examples, trace, annealing, and readback across arbitrary artifacts and mixed collections. The current procedure is in `Intake.xml`.

Read needed skills and knowledge while working in their functional scope. A prior visit or read receipt is not a prerequisite for using an available tool. Discovery, delivery, and retained context are different facts.

Purposeful assignments, peer questions, and events are allowed. Routine logs must not stream into agent context. Mailbox availability is a short notice such as "1 message waiting"; use the known mailbox-read capability to retrieve messages. Do not poll. Context and tool-surface monitoring belongs in the operator view.
```

## Appendix D — verification scope

Run `python tests/check_contract.py`, `python tests/check_tool_input.py`, and `python tools/verify_bootstrap.py`.

The checks cover the stored schema, native layer preservation, selected-project reference resolution, relationship uniqueness, name-length bounds, single source URI shape, command input, and the owner's delete/remediation examples. The bootstrap check verifies preserved source hashes and matching contract appendices. Current results are reported after the checks run; earlier results remain historical evidence.

These checks do not execute add/update/delete against a database. They do not prove intake fidelity, functional naming, technical wording, permissions, concurrent writes, MCP interoperability, or a running application. The acceptance scenarios in section 19 remain product requirements.
