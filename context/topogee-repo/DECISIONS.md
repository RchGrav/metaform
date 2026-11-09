# Decisions and boundaries

The full definitions and acceptance scenarios are in metaform/SPECIFICATION.md. Later founder corrections govern earlier documents.

## Settled requirements

- Product: Topogee Navigator; domain topogee.com; clean rebuild in RchGrav/topogee.
- Nested JSON is the functional namespace's document form; maps are stored in LadybugDB (R-4.1). Elements own their properties and layers. RE/PE are perspectives.
- `wants` is the functional knowledge layer: a dictionary keyed by provider address; each value holds the receiver-owned `why`, `how` and `intent` (2026-11-07: renamed from goal and function, ice removed, list changed to dictionary). One relationship per provider address per receiver; every target exists in the tree.
- name is the project term; name_length counts reversed trailing segments. Native plural-array layers retain native contents.
- Universal intake preserves functional intent across diverse artifacts. Explicit status un_built; no BKN diagnosis. Authored semantics and schemas remain protected against unrequested edits.
- Maps are stored in LadybugDB, written only by the functional map server (2026-11-07 default for the founder's confirmation: a map is the logical unit with its own queue, and maps are grouped as partitions of the project's database rather than one database per map; `docs/designs/storage.md`); Rust never writes map files itself. Settings and the project registry may be JSON (founder, 2026-11-07, correcting the 2026-11-03 record that put the map in JSON files; `metaform/SPEC.md` R-4.1). JSON is the default; SQLite can be used where tabular data fits better, and Ladybug where it is the better fit. A missing musl build is not a concern, because Claude Code and the other harnesses do not run on musl (founder, 2026-11-03). The rule behind this: always choose the best tool for the job, weighing the pros and cons and how it may be used in the future (founder, 2026-11-03). How data is stored and the tools an agent gets are not the same thing: the MCP server is not direct access to the data (founder, 2026-11-03: "how we store data and the tools an agent gets are not the same thing.. over there they treated the mcp server as direct access to the data"). Every store gets a write queue, even one that is not part of the chassis, and writes are queued fairly (founder, 2026-11-03: "write queues on everything even if its not the chassis itself and fair queuing on writes"). Shared authoritative storage, public DAO/shared services and independent module chassis. All features are modules.
- One Metaform tool accepts add/update/delete, an orphan query, and addressed reads. Read-only views are projections, not a second tool. Commands focus on one receiving entity and do not define storage layout. The tool name remains provisional.
- Progressive skill/context delivery, measured or honestly estimated context usage, and visible actual tool surface. No navigation/read-receipt gates or diagnostic floods into agent context.
- No recurring application polling. WebTransport control channel; selected browser/custom client is acceptable. No WebSocket fallback or adapter in scope. Reliable streams for required delivery; datagrams only where loss/reordering is semantically acceptable.
- Mailbox is lightweight: waiting-count notice plus a known explicit read. Purposeful assignments/events/messages remain allowed. MCP-event-to-chassis-local delivery support remains distinct from the excluded WebSocket fallback.
- Dynamic prompt-led agent coordination; worker/system/liaison launch, instructed non-launcher stop, dormant reuse governed by cache economics, persistent historical identities.
- Observed peer assessment only for active team work. Weights10/20/30/40, ratings0–5, bonus≤5, history arithmetic mean through105%, solo unscored. Preserve privacy.
- Feature commit in both modes; Full Auto lands/pushes/confirms/cleans, otherwise PR. Product mode does not override actual user authorization.
- Physical camera/depth3500mm/60°; virtual360° eight wedges,45° trigger/up-down angle, unsigned16-bit millimeters through65535. Consumer chooses actions.
- Multi-user access, isolated per-user focus/context, attributable changes and conflict-safe writes must be supported by the service design.

## Technical choices still to make

Runtime language (Python, Node/TypeScript or justified hybrid), WebTransport library/deployment,
public service signatures, the JSON file layout and transaction/conflict contracts,
project access/sharing, remaining add/update and native-array behavior, deletion of namespace subtrees,
orphan-query scope, multi-receiver remediation, and revision/retry binding,
active-work/receipt binding, incremental mailbox read/ack binding, ICE group persistence,
sensor coordinates/payloads and remaining module tool bindings.

These are engineering proposals to make concrete and test, not a request for the founder to reconstruct the design again.

## Source precedence

Current founder decisions → current specification → labelled technical proposals → preserved historical evidence.
Historical execution instructions are not automatically authorized actions. A passing shape test is not evidence of functional correctness.

## MCP tool-design session — 31 October 2026

Founder decisions recorded during the forge session:

- The initial discussion separated working and viewing tools. This is superseded by the founder's latest instruction: one Metaform tool. The process remains perspectival, focused on one receiving entity at a time. Intake is initial onboarding.
- Preserve the prescribed functional structure. It already abstracts the database. Do not introduce a separate representation or a `data` wrapper without a demonstrated need.
- Both receiver and provider exist at actual nested namespace locations under the selected project. The receiver's relationship references the provider by its project-relative dotted address. Each actual element owns its properties and native knowledge arrays, including `skills[]`, `memories[]`, `tasks[]`, and `inbox[]`.
- Try `wants`, `goal`, `function`, and `intent` as tool vocabulary. `wants` holds the receiver-owned provider relationships; `goal` expresses OP; `function` expresses the provider's encounter-specific EF. `intent` defines what the declaring entity plans to do with the substance to satisfy the overarching goal, with `send`, `receive`, and `both` as the discussed values.
- Founder's example: email client wants email server; goal is to send and receive mail; function provides email server service; intent is both.
- Retain CQU and the other authored definitions. The founder explains that generic alternatives lead models to answer person, developer, or user rather than infer the specific vested party for the artifact type. Familiarity alone is not a reason to replace a term.
- Use the July 28, 2026 MCP specification for protocol design. URI-addressed resources can supply generated views; the founder suggested a sparse tree showing element names. Rendering format and client remain unselected.

The founder proposed an outer `add` / `update` / `delete` operation around a receiver contribution, then illustrated the receiving address as its key. This is the working candidate, not a finalized input schema. Exact creation, update, deletion, and response behavior still need to be worked through. The assistant's proposed error rules, atomic submission details, and automatic local-view response have not been accepted as decisions.

The founder subsequently rejected the assistant's expansion into a multi-element declaration request: the submission had already been demonstrated, and data is not stored in that request format. The actual nested namespace remains the stored logical representation. Do not adopt the rejected example or its proposed `add` rules.

At the initial trial stage, the schema and prompt had not yet been changed. The founder subsequently authorized updating the specification, contracts, and intake prompt; the update below supersedes that state. Session history: [_bmad-output/forge/mcp-intake-tool-design/.memlog.md](_bmad-output/forge/mcp-intake-tool-design/.memlog.md).

### Authorized specification and intake update

The founder instructed: "consistenly update the spec for these changes including the intake prompt, write in clear simple technical english for the changed terms no llm register". This directly authorizes the current schema and prompt update. Preserve CQU and the remaining authored concepts and method.

The founder's [query note](metaform/docs/mcp-query-source.md), now stored in the project, supplies these command rules:

- `delete` with an addressed empty object deletes an element only after its incoming wants have been removed.
- `delete` with `wants: ["provider.address"]` removes the named receiver-owned relationship, not the provider element.
- A rejected referenced-element deletion returns `status: "error"`, a readable message, and an explicit remediation command.
- `orphaned: {}` queries unreferenced elements. Results are under the `orphaned` key; discovery does not delete them.
- An addressed empty object without an operation reads the element. Its fields are returned under that address.
- `update` with a property set to `null` removes that property. This supersedes the assistant's rejected null-based element-delete proposal.
- One `uri` on an actual element identifies the source entry point. Extra evidence belongs with the finding that needs it.
- Validate command input before mutation, then validate the resulting map against existing data. The input schema and stored-document schema have separate jobs.

The founder also clarified that `intent` is not in conflict with `goal`. The collision was the wording of intake step 6. With the authored terms restored, it now says that an EF satisfies an OP. Incorrect articles introduced by the term replacements are corrected separately.

The current files use wants/goal/function/intent. The project [metaform/Intake.xml](metaform/Intake.xml) is the current prompt. Maintain it in this repository. Earlier contract bytes are retained under `reference/contract-baseline-2026-10-30/`, with their original hashes in `source-register.json`.

### Term mapping: intake terms and stored names

The founder decided to keep the intake semantics unchanged and to store them under these names. Intake definitions (RE, PE, CQU, ICE and the others) are not changed by this mapping.

- Operative Purpose (OP) is stored as `goal`. It is what the receiver needs to achieve.
- Encounter Function (EF) is stored as `function`. It is what the provider has that achieves the receiver's goal.
- Information Flow Direction (IFD) is stored as `intent`. It is the substantial flow of information which satisfies the (OP) goal not including the request: `send`, `receive`, or `send_receive`.
- The Providing Element (PE) is recorded as the provider's address, a key in the receiver's `wants` dictionary.

Example: an email client wants an email server. Goal: send and receive mail. Function: the email server service. Intent: `send_receive`.

### Intent values and description

The founder set the third `intent` value to `send_receive`, because `both` is not clear. The values are `send`, `receive`, and `send_receive`. This replaces `both`, `sends`, `receives`, and `send-receive`.

The founder stated the full description of the field: "the substantial flow of information which satisfies the (OP) goal not including the request." The instructions must state "not including the request" explicitly.

### The project is the root object

The founder decided that the project name is the root object of the stored structure. Exported to JSON, the path to an element is `$.projectname.namespace.address.of.receiving.element`. One database can hold more than one project.

### Correction: preserve the authored reasoning vocabulary

The founder corrected the update: keep the paper's terms and semantics intact. The instructions must say how to record them, rather than replace them in definitions or reasoning. Restore the original concept definitions, examples, constraints, CQU rules, namespace rules, and OP/EF/IFD wording in the method. Step 6 retains only the agreed correction: an EF satisfies an OP.

Record the PE's address as a key in the RE's `wants` dictionary; record OP as `why`, the PE's encounter-specific EF as `how`, and IFD as `intent`. (Renamed from `goal` and `function` on 2026-11-07; see "Want fields are why and how" below.) This mapping changes field names, not the concepts. It supersedes wording that called OP, EF, and IFD merely explanatory terms for reading historical papers. The working prompt and repository copy carry the same correction.

### Founder constraints for the next build (3 November 2026)

These are stated by the founder and apply to every slice. They are not assistant proposals.

- **Chassis and modules.** The Python chassis, its settings system and its template-based module approach are the proven base. New features land as modules that use services exposed by the chassis. The earlier build stayed stable for about two months this way. (The language is superseded by "The chassis" below: Rust with Bevy, 2026-11-03. The module approach stands.)
- **Tool surface is capped.** The previous build grew to about 300 tools because the tooling specification was not tightly defined. Tool creation must be constrained by the specification. Tools serve context management, which is the core approach; that purpose must be stated plainly in the specification and in agent instructions. Every new tool needs a founder decision first.
- **Commit and worktree rules are kept.** The previous system provisioned a worktree for each piece of work, made automatic feature commits, and followed commit rules. The commit rules lapsed during tool reduction and must not lapse again. Preserve this pattern unless the founder changes it.
- **Source file size.** The target for typical source files is about 500 lines. A single file grew to about 16,000 lines in an earlier build and had to be split. Files over the limit are split before they grow further, and the limit is checked as part of the work.

### Project location and single-tool correction

The founder directed that this work live in the project and corrected the remaining separate-tool description. The current contract declares one Metaform tool for both changes and reads. The separate viewing-tool registry entry is removed. Read-only projections remain part of the design and can be presented as generated resources.

The current prompt is [metaform/Intake.xml](metaform/Intake.xml), the sequence diagram is [metaform/intake.mmd](metaform/intake.mmd), and the supplied query note is [metaform/docs/mcp-query-source.md](metaform/docs/mcp-query-source.md). Maintain these project files. The personal folder is the source of the supplied material, not a second location that other agents must update.

### Memory module (3 November 2026)

The founder decided that memory is a module with its own tool: "memories have an origination address, you can make a dedicated memory tool"; "make memories a module". This is the founder decision that a new tool needs (see "Tool surface is capped"). The one Metaform tool stays the only tool for the map; memory is a separate module, and tools are organized by module (metaform/SPEC.md R-5.26). The tool exists for context management: it keeps durable facts about the project at the addresses they come from. The memory commands are identical to the modelcontextprotocol.io memory server's. The tool shows a different memory graph depending on where the agent is: "the only way to read and write those memories is via presence at that address". A memory can link to any address or memory. The project-map `goto` command sets that presence (metaform/SPEC.md R-5.30). The requirement is metaform/SPEC.md R-5.29. The tool's name and commands are proposed in metaform/docs/designs/metaform-server-design.md.

### The chassis (3 November 2026)

The chassis is event driven, written in Rust, and uses Bevy (founder: "I would like to see the chassis be event driven, be in rust and use bevy"). This settles the language part of metaform/SPEC.md D-9. How modules connect to it is still open. Bevy's entity-component-system model matches TOPOGEE.md section 2, where functional addresses are entities and layers are components. The functional map server stays a standalone Node MCP server, and passes control of its integrated data to the chassis when the chassis is present (metaform/SPEC.md R-2.11).

### Naming: Topogee and Metaform (7 November 2026)

Topogee is a shared world where agents and people collaborate and build anything, including the world itself. It has the bones of a game, but it is not a game. Its design is `docs/designs/world-system-spec.md`. Metaform is the context tool for development agents: the functional map, the intake and the MCP server. This repository develops both. The founder: "the context engine is metaform"; "metaform itself we are creating as a context tool for development agents, so we are actively participating in the development of both."

The founder, refining it: "I'm calling topogee a game.. but it isnt, it has the bones of one but what it really is lands closer to a world where agents and users can collaborate and build anything, including the world itself.." (2026-11-07).

Older documents use "Topogee" for the context engine. Read that use as Metaform. On 2026-11-07 the founder approved renaming the documents an agent wrote: `metaform/SPEC.md` (its purpose statements), `metaform/docs/metaform-concepts.md` (formerly `docs/topogee-concepts.md`), `README.md`, `docs/README.md` and `docs/address-only-example.md`. Still the founder's call: `TOPOGEE.md` (the founder's opening statement), the T in TASTE, and "Product: Topogee Navigator" above. The founder's quoted words are never changed. `metaform/SPEC.md` keeps its file name, because the `topogee` command is the umbrella for both products and the specification covers the chassis and modules as well as Metaform.

### The Node server is a test harness (7 November 2026)

The Node server in `metaform/server/` was built in minutes to test the contract. It is not the design and is never a source for it. The founder said so when it was built: "this better not become the design we have one already". The design is the founder's documentation set, copied into the project as `metaform/docs/documentation-set.md`, which `metaform/SPEC.md` cites. The harness's flat store, earlier field names and the JSON storage that followed it are not the design.

### Want fields are why and how (7 November 2026)

A want record holds `why` (OP), `how` (EF) and `intent` (IFD), as R-3.4 and the founder's documentation set decided earlier. The founder: "why and how was reasoned as more universal ... it reads as correct and aligns to the original intake procedured as they are used in the descriptions.. and work across all types for intake"; "yes that decision was made a while back"; "wants why and how are the most universally reasoned terms possible". The intake's own concepts already define OP as "the why" and EF as "the how". Renamed on the founder's instruction in `metaform/Intake.md`, the recording labels of `metaform/Intake.xml` ("you can just replacing those words"), the schema, the tool contract, the examples, the contract tests, the Node test harness's interface and the Rust prototype. The Node harness keeps its database columns named `goal` and `function`, so the existing `roundtable` map still opens; it maps them to `why` and `how`.

### technical_name and the four roles (7 November 2026)

`technical_name` replaces `name_length`, and roles are Definitive, Supportive, Notable and Divergent, as R-3.4 and the founder's documentation set (3.1, 3.2) decided. The founder: "its obvious that needs to be done isnt it?" In `metaform/Intake.md`, the technical-name rule and the Divergent definition are the documentation set's own wording; the intake's tuned definitions of DE, SE and NE stay, relabelled Definitive (DE), Supportive (SE) and Notable (NE). In the examples, `technical_name` was computed from each address and its old `name_length`, so no value was invented. The validator checks the documentation set's TECHNICAL_NAME_ALIGNMENT_FAILURE and CANONICAL_NAME_COLLISION_FAILURE rules. The Node harness keeps its `name_length` column so existing maps still open.

### Anything keyed by a unique name is a dictionary (7 November 2026)

The founder: "be wary of my inpropere inclusion of square brackets on dictionaries"; "anything with a unique key by name is a dictionary not an array." Applied: `wants` is a dictionary keyed by provider address (the canonical map already stored it that way); the orphan scan returns a bare dictionary keyed by address (R-5.23); the layer listing read is `{".": {"layers": {}}}` (R-5.22). A list of addresses to remove (`delete ... wants: [...]`) and true lists such as `memory`, `sources` and root `skills` stay lists. Changed in `metaform/Intake.md`, the schema, the tool contract and its appendix copies, the examples, the validator and contract tests, the Node test harness and the Rust prototype. `metaform/Intake.xml`, the tested record, and the founder's documentation set copy are unchanged. The founder: "I architected this as nested json because the namespace is nested"; in Ladybug the nesting and the wants are edges (R-4.16).

### ICE is superseded (7 November 2026)

ICE is gone from the intake and the stored data. The founder: "ICE was superceded"; "the DE <-> SE relationship is the inseperable boundary". The Supportive role carries coupling (`metaform/SPEC.md` R-3.14, decided earlier: "I'm even saying drop ice"). Removed from `metaform/Intake.md` (the field, the concept, the Evaluate ICE step and the annealing and verification clauses), the schema, the tool contract, the contract tests and the Node harness's interface. `metaform/Intake.xml` is the tested record from before the change and keeps it.

### Where Metaform lives (7 November 2026)

Metaform is tested and maintained in this private repository, in its own project folder, `metaform/`, with its own specification. It is used and proven here while it is refined for general development, and it later replaces the earlier private `metaform` repository. The intake procedure and its semantics are well tested and stay protected. The founder: "For now we are testing and maintaining metaform as part of this private repo to later replace the existing private metaform repo. so we keep metaform here in a project folder for it with its own specs while simultaneously using and proving it refining it for general development use, the intake procedure itself is well tested over 6 months and many intakes as well as the semantics."

### Root during development, and AgentSight as a service (6 November 2026)

AgentSight here is an example; the point is that agents can test their installers, and that background processes run without systemd.

The founder: "For development I was allowing root mainly for installing tools we may need along the way, in a real deployment I dont see that being the case but for the purposes of testing I would like to see the agents able to test their installers and make them work, for instance to install agent sight as a service so it persists for monitoring agents."

- Root on the development machine is for installing tools. A deployment does not give agents root.
- Agents may test their installers during development and make them work.
- AgentSight is installed as a service that persists, so agents can be monitored without the monitoring program itself running as root.

Proposed design (agent's choice, for the founder's review):

- A small root service runs the AgentSight probes. It is the only process holding eBPF privileges. It does not use systemd (founder: "we dont need to use systemd for this..").
- It listens on a Unix socket under `/run`. An unprivileged monitor, such as Roundtable's `agent-monitor`, connects and asks to watch a process id.
- The service checks the caller with `SO_PEERCRED` and watches only processes the caller owns. Any other process on the machine cannot use it to watch other users' processes.
- The service runs as a background process under the founder's HoldOn (`RchGrav/HoldOn`, "more than nohup, less than systemd"): `hold -d --name <name> --restart ...`. HoldOn gives it a durable call ID, captured logs, `hold end`, and `hold <name>` to start it again from its recorded recipe after a machine restart. Code may also be taken from HoldOn, or a version of it compiled for background processes (founder: "you can steal code from my rchgrav/onhold project or compile a version of this for background processes"). HoldOn is Apache-2.0 and written in C.
- One installer places the service, starts it through HoldOn, ends it and removes it. The installer is idempotent.
- Roundtable and every agent harness keep running as the normal user.
- The installer is tested on the development machine.

### The service launcher (7 November 2026)

The project builds its own launcher for starting services and assigning process permissions. It is a CLI command, customized from the approach of the founder's HoldOn (`RchGrav/onhold`), and bundled with the project. HoldOn itself is not used and its code is not vendored: the parts the launcher needs are taken out and customized. The founder: "we will be creating our own controller for launching services and assigning process permissions... think of this as a cli command we will be customizing to be our service launcher.. we are not using the tool itself we are separating what we need and customizing it to be the launcher we bundle so we are not vendoring it". This replaces "runs as a background process under the owner's HoldOn" in the AgentSight design above: the AgentSight service starts through this launcher.

The core is customized completely for this project's purpose, and HoldOn is chosen because that core is well tested (founder: "we are completely customizing the core for our purpose... its well tested so it should suit us just fine"). HoldOn's tests are part of what is taken: `metaform/tests/test_hold.sh` (about 5,500 lines) checks behavior through the CLI, and the C unit tests check the log index. Keep the tests for each part that is kept, changed to match the customized commands.

Accepted by the founder on the design reviewer's recommendation, covering the parts below and the order for permissions (founder: "If you feel it aligns well with the project goals like I do then yes I think its the right move"). Take these parts from HoldOn:

- **No daemon.** Every command reads the recorded state from disk and checks it again before it acts. This matches "no recurring application polling" and the rule that background processes run without systemd.
- **Identity checked before every signal.** At launch, the record stores the process group, the session, the boot id, the process start time and the executable's inode. Before it stops a service, the launcher checks these against the live process table. If they are stale or unclear, it refuses. A reused process id is never signaled.
- **A launch is recorded only if it happened.** A close-on-exec pipe reports whether `exec` succeeded. If the record cannot be written, the process group is ended and the launch is rolled back.
- **The whole process group is signaled.** An agent harness's child processes stop with it.
- **A private record and a redacted public index.** A root service, such as AgentSight, is visible to normal users without its arguments, environment or log paths. A normal user cannot read what a root service runs.
- **Recipes and restart.** A service starts again from its recorded recipe after a machine restart.
- **Logs with an index file.** Captured output can be read, followed and replayed by tools other than the launcher.

What HoldOn does not do, and the launcher must add: assigning permissions. HoldOn runs host processes as they are and isolates nothing. The order, smallest first: run each service as a named user; give it only the Linux capabilities it needs (for AgentSight, `CAP_BPF` and `CAP_PERFMON` in place of full root, Linux 5.8 and later); set `no_new_privs`; then add cgroup limits and Landlock file rules when a service needs them. Each service's permissions are in its recipe, so they are recorded and inspectable.

**Language: C (founder, 2026-11-07).** The launcher keeps HoldOn's core in C. The founder: "Yes keep it in C its rock solid". Split the files that pass the project's 500-line target as they are customized: `src/runtime/start.c` is 914 lines, `src/core/logidx.c` 826 and `src/runtime/signal.c` 753. The 2,111-line log viewer (`src/viewer/tty.c`) is probably not needed.

**Permissions live in the settings system (founder, 2026-11-07, accepting the recommendation).** The settings system holds each service's permissions, and the launcher reads them when it writes the recipe. The recipe records what was applied at launch. This keeps to "do not bypass the chassis or the settings system" (CLAUDE.md).

**Correction to the line above (founder, 2026-11-07: "yes of course, thats literally a best practice"; `docs/designs/service-launcher.md` SL-4.1).** For a service that runs as root, the user's settings file cannot be the authority, because the user and every agent running as the user can write it. The settings system still declares and shows the permissions; an elevated install step copies them into a root-owned recipe, and the root launcher reads only that recipe.

**First services: AgentSight and the Metaform server (founder, 2026-11-07, accepting the recommendation).** AgentSight is the one service that needs root today. The Metaform server already has CLI commands to stop and restart it (`topogee metaform server status | stop | restart`). Agent harnesses, the chassis and the Topogee world server come later. The founder: "yes proceed with your recommendations".
