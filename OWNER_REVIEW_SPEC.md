# Metaform: specification for owner review

## 1. Document status

| | |
|---|---|
| Prepared | 2026-11-08, by an agent, from the materials gathered into this folder |
| Status | **Draft for the owner's review.** It is not an approved specification and does not replace `metaform/SPEC.md`. |
| Evidence reviewed | `metaform/SPEC.md`, `metaform/docs/documentation-set.md`, `metaform/Intake.md`, the schema and tool contract, `metaform/docs/designs/metaform-rust.md`, `context/topogee-repo/DECISIONS.md`, `TOPOGEE.md`, the owner-statement files, `docs/designs/storage.md`, the owner's notes in `context/brain/`, and the git history up to b65dba2 |
| Scope | Metaform: the intake, the functional map, the one tool and the map server (the functional map server of `metaform/SPEC.md` section 4.2). Roundtable is covered only where it touches Metaform (section 5). |
| Complete? | **Partial.** The earlier private Metaform repository and the old Roundtables module are not on this machine. Several owner decisions are still open. The newest owner notes in `~/brain` were never carried into the project (questions Q3 and Q4). |
| Freshness | This reflects the materials as of 2026-11-08. `SPEC.md` says the owner has not reviewed it. |

**Labels used:** **Confirmed** means the owner stated it (the source is given). **Proposed** means an agent or a working document suggested it and the owner has not confirmed it. **Open** means the owner must decide it. **Stated** means a source document says it. **Inferred** means the preparer's reading of the evidence. **Proposed by the owner** means the owner suggested it and has not confirmed it.

### Summary

Metaform gives development agents a map of what a project *does*, not of its files. An intake agent reads the project, which can be code, a specification, a manual or anything else, and writes a tree of functional elements. Each element records which other elements it needs, why, and how. Agents then work from a small, relevant slice of that map instead of rereading the whole project. The goal is to spend less of an agent's reasoning on orientation, so that its reasoning is kept for the work, and to stop agents from changing things they do not understand. The saving is not a token saving or a money saving (owner, 2026-11-09; `metaform/SPEC.md` R-1.4).

## 2. The need, the users and the goals

**The problem.** An agent has a finite amount of reasoning: a limit on how many things it can track and understand at once. Orientation in a project uses part of that reasoning and wastes context, and the agent still does not get the whole picture. Agents also make unsafe changes when they do not understand what a part is for. **Confirmed** (`TOPOGEE.md` opening; the owner: "Before anything can mutate it needs to fully understand what a thing is").

**Intended users**
- Development agents working in a project (Claude Code, Codex and other harnesses). **Confirmed.**
- The project owner, who reviews and refines the map and the specification. **Inferred.**
- Several people and agents at once. Multi-user access with conflict-safe writes is required. **Confirmed** (`DECISIONS.md` settled requirements).

**Goals**
1. Record a project's functional form, for any kind of project, greenfield or brownfield. **Confirmed** (`SPEC.md` §1, R-1.2).
2. Take in a specification, refine and organize it, and export it again in improved form (a round trip). **Confirmed**, not built.
3. Act as a "formboard" that helps agents realign code that is hard to refactor. **Confirmed.**
4. Give each agent only the context it needs for its place in the map, delivered progressively. **Confirmed** (`DECISIONS.md`, `TOPOGEE.md` §3).
5. Measure context use consistently, with and without Metaform. **Confirmed** as a goal (R-1.3). The measurement method is proposed.

**Non-goals**
- Metaform is not a record of code. File names, languages and syntax stay out of the functional map. **Confirmed** (`TOPOGEE.md` §1).
- It does not give agents direct access to the database. **Confirmed:** "how we store data and the tools an agent gets are not the same thing."
- It does not grow a large tool surface. A previous build reached about 300 tools. New tools need an owner decision. **Confirmed.**
- It does not use recurring polling, and it has no WebSocket fallback. **Confirmed.**
- Temporary foundations are not acceptable. **Confirmed** (R-1.1).

## 3. What users experience

These are written from the agent's and the owner's point of view.

1. **Intake.** One specialist agent runs the owner's intake procedure on a project. The project's functional elements appear in the map, under dotted addresses such as `code.server.world`. Exactly one element is the Definitive one, the thing the project is. **Confirmed** (R-2.10, R-3.13).
2. **Orienting.** An agent asks for the project index (`{".": {}}`) and sees the shape of the whole project with no detail. It then moves to its element (`goto`) and receives a summary sheet once, then only what changed. **Confirmed:** the index (R-5.11). **Proposed:** the exact form of `goto` (R-5.30).
3. **Changing the map.** An agent adds, updates or deletes an element or a relationship with one command through one tool.
   - The system refuses changes that would break the map, for example deleting something others still depend on.
   - Each refusal says why and gives the command that would fix the problem.
   - **Confirmed** (the owner's query note; R-5.4 to R-5.8).
4. **Finding loose ends.** An agent asks for "orphaned" elements, which are ones nothing refers to. Discovery does not delete them. **Confirmed.**
5. **Being told about changes.** Agents that subscribe are told when the map changes. Nobody has to keep asking. **Confirmed** (R-4.10). Built.
6. **Knowledge layers (not built).**
   - Skills, memories, tickets, sources and messages are attached to elements as separate layers.
   - An agent at an element sees the layers that apply there, including ones inherited from above. **Confirmed** in principle.
   - The owner's "unified layer approach" is expected to replace the current layer section. **Stated** (`metaform-rust.md`).
7. **Memory (not built).** Memories belong to the address they came from. An agent can only read or write them by being present at that address. **Confirmed** (owner, 3 Nov).
8. **Specification round trip (not built).** A specification goes in, is refined in the map, and comes back out as a specification. **Confirmed.**

## 4. Requirements

### 4.1 Confirmed functional requirements

**The map**
- The map is a nested tree. The project name is the root. **Confirmed.**
- Each element has:
  - `technical_name`, derived from the address
  - `name`, the project's own term, which must differ from `technical_name`
  - `role`: Definitive, Supportive, Notable or Divergent
  - `uri`: one source entry point
  - `status`: for example `un_built`
  - `wants`
- Each want is keyed by the provider's address and holds three things:
  - **why**: the receiver's purpose
  - **how**: what the provider supplies
  - **direction** (formerly **intent**): which way the substance flows, not counting the request: inbound, outbound or two-way
- There is one relationship per provider per receiver, and every provider must exist in the map.
- **Confirmed** (`DECISIONS.md` 7 Nov: "Want fields are why and how", "technical_name and the four roles", "Anything keyed by a unique name is a dictionary").
- ICE is gone. The Definitive–Supportive relationship is the inseparable boundary. **Confirmed** (7 Nov).
- CQU is kept as an intake concept but is not a role. **Confirmed.**

**The tool**
- There is one Metaform tool for the map. It handles add, update and delete, the orphan query and addressed reads. Read-only views are projections, not extra tools. **Confirmed.**
- Command input is checked before any change. The resulting map is then checked against the stored data. **Confirmed.**
- Memory is a separate module with its own tool, since tools are organized by module. **Confirmed.**

**The intake procedure**
- The intake procedure and its meanings are protected. They are proven over six months and many intakes. Agents must not change them without the owner's direct instruction. **Confirmed.**

**Storage**
- Maps are stored in LadybugDB, written only by the map server. **Confirmed** (7 Nov).
- How maps are grouped into databases is a default awaiting confirmation (Q1).
- Every store has a write queue, and writes are queued fairly. **Confirmed.**

**The server and the build**
- The map server is built in Rust. The Node server is only a test harness. **Confirmed** (7 Nov).
- The chassis is event-driven, in Rust, using Bevy. Features are modules on the chassis. **Confirmed.**
- Source files stay near 500 lines. **Confirmed.**
- Work uses a worktree and feature commits for each piece of work. **Confirmed.**

### 4.2 Quality expectations

- **Reliability:** a write that has been acknowledged survives a crash. **Proposed** as a test and **built**: the SIGKILL tests in `metaform/verification/`.
- **Efficiency:** no recurring polling, single delivery of context blocks, and honestly measured or estimated context use. **Confirmed.**
- **Security and privacy:** agents see the form, never the store. Peer assessment keeps data private. Which identity the server trusts is **Open** (D-8).
- **Accessibility:** not specified in the available materials.
- **Performance targets:** not specified in the available materials. Measured figures exist in `docs/designs/storage.md`, but they are not requirements.

## 5. Scope, dependencies and constraints

**In scope:** the intake, the map, the one tool, the map server and store, the CLI equivalent (`metaform call`), and the layers and memory modules when designed.

**Specified elsewhere or not yet** (`SPEC.md` §11):
- the Composer and Facilitator pipeline
- ACP harness control, agent names and inboxes (the agents module)
- the context-threshold handoff at 50% and 65%
- the mutation framework
- how modules connect to the chassis

**Dependencies**
- **LadybugDB.** Its concurrency and crash behavior were measured in experiments.
- **The MCP protocol, version 2026-07-28.**
- **The service launcher (optional).** It lives in the Topogee repository and is not copied here.
- **The owner's source notes in `~/brain`.** Some are newer than the project copies.

**Roundtable connection.** The owner wants agents to be able to own a Metaform map of what they intend to build, and to run a roundtable of agents on it. The map's owner leads the table and can end it. **Proposed by the owner** (2026-11-06, `SPEC.md` §11). Roundtable's own map is already a Metaform map, and it was used to test layers (`roundtable/metaform.json`).

**Constraints**
- The owner's terms stay. Familiarity alone is not a reason to replace a term.
- Communication follows `TASTE.md`.

## 6. Acceptance criteria

**From the materials** (`SPEC.md` §9, Proposed):
- A client connects using protocol `2026-07-28`.
- `{".": {}}` returns the whole project's index, including `upstream` and `downstream`, with no detail beyond the Definitive mark.
- A field that belongs to no group and is not a registered layer is refused.
- When layers are built: a layer at the root reaches every element below it but not `upstream` or `downstream`. An element can switch a layer off, and its child can switch it back on without affecting siblings.
- An exported map equals the imported document, apart from the open `wants` shape question (D-4).
- Each build step ends with its tests passing, with at most five tests per feature, through the public interface.

**Newly suggested** (**Proposed**, not established):
- A test intake with `metaform/Intake.md` 3.1 on a known project gives exactly one Definitive element and no validation failures.
- Deleting an element that others still want is refused, with a remediation command that works when it is run.
- Two agents writing to the same map at once both have their writes kept, in a fair order.

## 7. Questions for the owner

Each question says what it affects.

1. **Q1. Storage grouping.** Should maps be stored as partitions of one database per project (the current default), or as one database per map? This affects the store layout and any migration. *Recommendation in the materials:* partitions (`storage.md` 2.2).
2. **Q2. Direction.** *Answered 2026-11-08:* the field is now `direction`, with the values `inbound`, `outbound` and `two-way` (`SPEC.md` R-3.6). *Applied 2026-11-09* on your instruction to the intake, schema, tool contract, canonical map and both servers. Old Rust databases must be cleared and rebuilt.
3. **Q3. Your newer documentation set.** You edited `~/brain/Universal Intake & Layer Architecture Documentation Set.md` on 7 Nov after it was imported. In the example, `wants` became a dictionary, and root `skills` lost its brackets, which leaves broken JSON and contradicts "root skills stay a list". Should the project copy be updated, and should `skills` stay a list?
4. **Q4. Your newer query note.** `~/brain/mcp_query.md` adds an extra query item, and a definition of `name` as an alias for the address term. Should these go into the spec?
5. **Q5. `TOPOGEE.md`.** It still uses the old role names, `goal`/`function` and `name_length`, and it calls the context engine "Topogee". Will you update it, or should it stay as a historical opening statement? Should "Product: Topogee Navigator" be retired?
6. **Q6. Where the governing documents live now.** `DECISIONS.md`, `AGENTS.md` and `CLAUDE.md` governed both products in the old repository. Should Metaform get its own decisions file here, and should the stale lines (Node server, Python/Node language, `Intake.xml` as current, nonexistent `topogee metaform` commands) be corrected?
7. **Q7. `collection` as a root scope.** The procedure has seven root scopes, and the documentation set has six. Which is right? (D-11)
8. **Q8. Layers and chaining.** The layer section waits on your "unified layer approach", and chaining waits on your choice of contract form (proposed: an explicit `/` address form). When can these be specified?
9. **Q9. Missing sources.** Should the earlier private repository (now `RchGrav/metaform-archive`), the old Roundtables module (`metaform-tasks`, not on this machine) and the live map databases (`~/.metaform`, `~/.metaform-rust`) be brought into this folder?
10. **Q10. Server identity.** Which identity should the server trust, given that MCP client names are self-reported? This blocks per-agent projects and per-user focus. (D-8)

## 8. Traceability

| Requirement | Source |
|---|---|
| Purpose and goals | `metaform/SPEC.md` §1 (owner, 2026-11-07); `context/topogee-repo/TOPOGEE.md` |
| Map fields, roles, why/how, dictionaries, no ICE | `context/topogee-repo/DECISIONS.md`, 7 Nov sections; `SPEC.md` R-3.4, R-3.13, R-3.14 |
| One tool, command rules | `DECISIONS.md` "MCP tool-design session"; `metaform/docs/mcp-query-source.md` (**older than** `context/brain/mcp_query.md`) |
| Storage in LadybugDB, fair queues | `DECISIONS.md` settled requirements; `SPEC.md` R-4.1, R-4.7; `context/topogee-repo/docs/designs/storage.md` |
| Rust server, Node as harness | `SPEC.md` R-4.6; `DECISIONS.md` "The Node server is a test harness" |
| Intake protected | `context/topogee-repo/AGENTS.md`; `DECISIONS.md` "Where Metaform lives" |
| Memory module | `DECISIONS.md` "Memory module"; `SPEC.md` R-5.29 |
| Layers | `SPEC.md` §6 (**to be replaced** by the owner's unified layer approach) |
| Build status | `metaform/docs/designs/metaform-rust.md` "Progress"; `context/topogee-repo/.design-review/README.md` |
| Roundtable connection | `SPEC.md` §11; `roundtable/docs/egm-map-layers.md` |

**Stale or superseded sources:**
- `metaform/SPECIFICATION.md`, the older draft.
- `metaform/docs/designs/metaform-server*.md`, superseded storage.
- `metaform/Intake.xml`, the earlier prompt.
- `context/topogee-repo/Intake.md`, a stray older copy.
- Early sections of `DECISIONS.md`.
- `AGENTS.md`, `DEVELOPMENT.md`, `docs/README.md`.
- `metaform/docs/documentation-set.md`, behind the owner's own copy.

The full conflict list is in `PROJECT_CONTEXT.md` §7.
