# Metaform agent surface: jobs carried by a nonce, over CLI and MCP

Status: proposal, 2026-09-23, written by metaform-68 for mgm-main-f8. It is not decided. Below it are two superseded drafts: the chassis-with-modules draft from earlier today, whose plugin mechanics this draft reuses, and the two-server design.

## The model

As mgm-main-f8 passed on its understanding from the owner on 2026-09-23. The owner asked for this in place of his own quote.

Metaform is the one place an agent goes for its work. A worker never learns Metaform as a whole. It sees only what its job gives it.

The orchestrator sets up the job. It chooses the instructions, the inputs, the knowledge layers the worker may see, and the commands the worker may use. Metaform shows the worker nothing outside that job.

The nonce is the handle for the job. The orchestrator tells a worker only one thing: "run metaform <nonce>". The workflow's own text then reaches the worker exactly as it was written, and the orchestrator never rewords it. That makes a prompt chain across agents repeatable. It also works where one harness cannot hand work to another: the orchestrator gives the next agent the next nonce. Controlling writes is a second job of the nonce, not its main one. Provenance records who changed what, and under which nonce.

The worker moves through its job from the nonce:
- `metaform <nonce>` always shows where it stands: its instructions, its commands and its current step.
- `metaform <nonce> list` shows its inputs.
- `submit` hands in the answer and moves on to the next step.
- `metaform <nonce> next` moves on without submitting, when the same agent does several steps in a row.

MCP is a second way into the same job, never a different or bigger one. Anything a worker can do over MCP it can also do from the CLI, so an agent without MCP loses nothing. The CLI, or the orchestrator, also gives the worker what it needs to reach its job through the MCP server. The exact form of that is open.

The orchestrator's own view is the full one: the base text on how to use Metaform, and each module's statement of what it is for.

## What exists today, against this model

Checked in `src/metaform/contextual_cli.py`, `src/metaform/help_pages.py`, `src/metaform/assignments.py`, `modules/workflows/execution.py` and `modules/mcp/server.py` on 2026-09-23.

| Need | CLI today | MCP today | State |
|---|---|---|---|
| Status | `metaform <nonce>` prints the module and its description, then nonce, status, step and project, the exact issued prompt, the knowledge references, the submission header, and a command list. | `assignment` returns the prompt, header, context, producer and the module's operations. `status` returns the assignment, jobs and events. | Exists. The command list is not the task's list: see "Commands per job". |
| Commands per job | The command list is every command of the nonce's module that its module settings make visible, plus the fixed chassis set `submit, complete, abort, jobs, call, operations, records, provenance, namespace, events, help`. `call` runs any operation of the module. | `operations` and `call` expose every operation of the module. | Missing. Visibility is set per module, never per job. A workflow step's nonce belongs to module `workflows`, so its holder sees `create`, `start`, `intake` and the rest. |
| Layers per job | No worker command applies a layer choice. `records`, `namespace` and `provenance` read the whole project. | `namespace` and `resolve` read any address or revision in the project. | Half. At issue time a workflow step's rendered prompt applies `layer_select` from the step or the run. The worker's read commands do not. |
| Next on the same nonce | None. | None. | Missing. Each workflow step issues its own assignment with its own nonce. One nonce holds one step. |
| Submit moves to next | `metaform <nonce> submit --input <file>` records the answer against the header. | `submit` does the same. | Partly. While a run's drive job is active, it sees the submission, seals the answer and issues the next step under a new nonce. The submitter is not told that nonce. |
| List inputs | None. | `assignment` includes the evidence, with bindings and input references, as raw references. | Missing as a navigation command. |
| Same surface on CLI and MCP | Chassis commands `jobs`, `records`, `provenance` and `events` have no MCP tool of the same name. | `resolve` and `assignment` have no CLI command of the same name. | Close, not equal. |
| Provenance | Every operation run under a nonce writes a producer record naming module, operation and nonce. The MCP server also records its pid against each nonce it serves. | Same records. | Exists. Which agent held the nonce is known only through the nonce and the pid. |
| Orchestrator text | None. The main menu is for a person. | One instructions string, written for an assigned worker. | Missing. |
| Reaching the job over MCP | The status page prints a "Submission header", which `submit` requires unchanged. The harness passes `--nonce` to the MCP server it launches. | `assignment` returns the header, and `submit` requires it. | Open. The form the CLI or orchestrator gives a worker for MCP is being confirmed. |

## The job

A job is what the orchestrator sets up and the nonce names. It is today's activation assignment with four things added. Everything else about the assignment stays.

| Part | Today | Added |
|---|---|---|
| Instructions | `prompt`, stored exactly and shown exactly | nothing |
| Module and project | `module`, `project` | nothing |
| Write scope | `scope`, added in f469fe4 | nothing |
| Commands | the module's visible commands | `commands`: the exact list of commands the holder gets. Each names a command that a module declares for jobs, as described under "Plugin contract". |
| Knowledge layers | none on the assignment | `layers`: the layer selection the holder's reads and rendered context use, in the knowledge module's existing selector form. |
| Inputs | `inputs` and `bindings` in the evidence | `list` shows them. Nothing new is stored. |
| Steps | one step per nonce | `steps`: an ordered list of step instructions on the same nonce, with the current step index. |

The orchestrator sets up a job with the existing activate command, with new options:

```
metaform modules activate <module> --project <project> --prompt <text>
    [--scope <address> ...] [--command <name> ...] [--layer <selector> ...]
    [--step <text> ...]
```

- No `--command` gives no task commands beyond the navigation commands. A worker gets only what the orchestrator names.
- No `--layer` gives no layers. The worker then reads the functional core and nothing layered on it.

These two defaults follow "choose exactly what knowledge layers are available" and "metaform itself is supposed to be limited". They are the point to confirm.

## The worker's surface, the same on CLI and MCP

| CLI | MCP tool | Does |
|---|---|---|
| `metaform <nonce>` | `status`, and also the server instructions for a connection launched with `--nonce` | The current step's instructions, exactly as issued, then the step number and count, the task's commands, and the submission header. |
| `metaform <nonce> next` | `next` | Moves to the next step on the same nonce without submitting, and shows it. When no steps remain, it says so and changes nothing. |
| `metaform <nonce> submit` | `submit` | Records the answer for the current step. If the job has another step, it moves there. If a workflow run issues the next step under a new nonce, the reply names that nonce. |
| `metaform <nonce> list` | `list` | The job's inputs: each binding's address and readable name, with its exact references. |
| `metaform <nonce> <command>` | `<module>_<command>` | Each command the job granted, reached through the same module operation. |
| `metaform <nonce> complete`, `abort` | `complete`, `abort` | Unchanged. |

Nothing else is shown to a nonce holder. `records`, `namespace`, `provenance`, `events`, `jobs`, `operations` and `call` stop being fixed chassis commands on a nonce. They become commands an orchestrator can grant. Reads that a job grants apply the job's `layers`.

MCP parity rule: every job command is one module operation. The chassis presents it as a CLI subcommand and as an MCP tool from the same declaration, so the two cannot drift apart. The MCP tool name is `<module>_<name>`, following the naming rules kept from the superseded draft below. The CLI name is `<name>`, because a job's commands come from its one module.

## The orchestrator's connection

- The CLI without a nonce keeps the main menu, which is where jobs are set up.
- The MCP server started without `--nonce` serves the orchestrator. Its instructions are the base text below, then each module's `mcp_instructions` in module id order. Its tools are the job setup tools and each module's orchestrator commands, named `<module>_<name>`.
- Draft base text:

> Metaform keeps a project's recorded account of what each part is for. It also carries work between agents without rewording it.
>
> To hand work to another agent, set up a job: its instructions, its steps, the commands it may use, the knowledge layers it may see, and the addresses it may change. You get a nonce. Tell the agent only: run `metaform <nonce>`. If the agent has this MCP server, tell it to connect with that nonce instead. Either way it sees the job exactly as you set it, and nothing else in Metaform.
>
> The agent moves through its steps with `next` and `submit`, and sees its inputs with `list`. Every change it makes records the nonce, so provenance shows who changed what under which job. Revoke a job with `metaform <nonce> abort`.
>
> Each module below says what it is for and which commands it can give a job.

## Plugin contract

Being built first, as agreed with mgm-main-f8 on 2026-09-23. It is one list for now, because the split between job commands and orchestrator commands belongs to the open job model.

| Field | Type | Meaning |
|---|---|---|
| `purpose` | `str`, default `''` | The module's statement of what it is for, shown to the orchestrator. |
| `agent_commands` | `tuple[AgentCommand, ...]`, default `()` | Commands the module offers agents. One declaration serves the CLI, as `metaform <nonce> <name>` in the module's activation menu, and MCP, as the tool `<module>_<name>`. |

`AgentCommand` fields: `name`, then `operation`, which must be a key of the module's `operations`. `change`, a `bool` or a callable of the call's arguments, defaults to `True`. `addresses` is a callable of the call's arguments returning the addresses the call writes, or `None`. `description` defaults to the operation's docstring. `api_version` stays 1, for the reason given in the superseded chassis draft below.

When the job model settles, one field on `AgentCommand` can say which surface offers the command.

## Authority

Controlling writes is the nonce's second job. The write check from the superseded draft still holds on a nonce: a granted command whose `change` is true runs only while the nonce is live, only in its project and module, and only inside its scope. Its producing record names the nonce.

Open question (c): does the orchestrator's own connection need a nonce to change the project? The Authority section below says "agents need to be given a nonce from the orchestrator to make changes in their project otherwise the mcp server wont allow modifying anything but agent memories". The orchestrator is the one who issues nonces. The choices:
- **c1**: the orchestrator's connection changes the project without a nonce, as a person at the main menu does. Its changes record the connection's producer.
- **c2**: the orchestrator issues itself a nonce for its own changes.

## Options (a) and (b)

- **(a) is settled by this model.** A worker sees only its job's surface: the job's instructions and steps, its granted commands, its layers, and the navigation commands. This is a1 of the superseded draft, narrowed from the whole module to the job.
- **(b) matters only for the orchestrator's connection.** A worker's surface is chosen by its job, so which modules contribute cannot reach a worker. For the orchestrator it still decides whose purpose text and commands appear: every enabled module, which is b1, or only the modules enabled for the project, which is b2 and needs a per-project setting that does not exist today.
- **What a worker is given to reach its job over MCP** stays open until the owner confirms its form.

## Acceptance tests, written first

1. A job set up with a prompt, two steps, one granted command and one layer. `metaform <nonce>` shows step 1's instructions byte for byte, "step 1 of 2", exactly the granted command plus the navigation commands, and the header. Nothing else is listed.
2. The MCP connection launched with that nonce lists exactly the same commands as tools and returns the same instructions. Every CLI command on that surface has an MCP tool, and the other way round.
3. `next` moves to step 2 and shows its text exactly. A second `next` changes nothing and says no steps remain.
4. `submit` on step 1 records the answer and moves to step 2. On a workflow step, the reply names the next step's new nonce.
5. `list` shows the job's inputs with their addresses and exact references.
6. A command the job did not grant is refused on the CLI and absent over MCP, even if the module offers it.
7. A granted read under a job with a layer selection returns that layer's items and no item from an unselected layer. A job with no `--layer` returns no layer items.
8. A granted change command writes with the nonce in its producing record, and is refused outside the scope or after `abort`.
9. The orchestrator connection's instructions are the base text, then each module's purpose in module id order.

Tests 1 to 7 fail today, because `next`, `list`, `steps`, `commands` and `layers` do not exist. Test 8 is covered by the uncommitted workflow MCP work once it moves to job commands. Test 9 fails because there is no orchestrator text.

## Four rules for every record

Settled on 2026-09-23, as mgm-main-f8 passed them on. They apply to the whole design.

1. **One set of navigation tools.** The core map is navigated with the same tools as the memory graph: open a root, follow its joins, search. The functional map is a graph of roots and purpose joins, and the memory tools work across it, not only on memories.
2. **The core is immutable.** It changes only by a correction: a new revision of the corrected record. The prior revision stays readable, and nothing is edited in place. A correction needs an orchestrator nonce. A memory does not.
3. **The metaform is its own provenance.** Who produced what, under which nonce, from which inputs, is recorded as joins in the metaform, not in a separate log.
4. **Every record is a join owned by its receiving element.** Memories, relations, layer items, findings, corrections and provenance all follow this.

### How provenance is recorded today

Checked in `src/metaform/production_joins.py` on 2026-09-23.
- Every operation has a producer. Its record is a `production` join at `data.provenance` in its project, with module, operation, nonce, parent, status, inputs, dependencies and outputs.
- Every output also gets a `provenance` join on the output's own owner. It names the producer, the output and the inputs.
- Writes made inside an operation through `data.put` or the namespace service take this path. So do the assignment writes in `src/metaform/assignments.py`.
- Records outside the metaform: project registration in the `plugin_projects` table, and module settings. Neither is a project record. Whether jobs and event deliveries reach the metaform as joins is not checked.

## Records in this plan, against rule 4

| Record | Owned by today or as first planned | Receiver-owned form |
|---|---|---|
| Purpose join from an intake or import | the receiving element | already receiver-owned |
| `intake.object` | the element | already |
| `intake.provenance` companion | the receiving element | already |
| `production` join | `data.provenance`, the project's provenance object | already. The receiver is the project's provenance record. The per-output `provenance` join is on the output's owner. |
| Layer definition, `knowledge.layer` | the layer's own address | already. The layer is its own receiver. |
| Layer item, one per practice, finding or question | first planned as a source join stored under the layer | a join owned by the item's target address, with the knowledge.attachment on that same target, as a memory is today |
| Layer item aimed at a join | first planned as a source join under the layer | owned by the join's owning element, with `subject` naming the join |
| Memory | the root it is about | already, in `knowledge.memory.remember` |
| Memory relation | first proposed on the object owning the "from" memory | a join owned by the receiving root, with the other root as `provider` and the verb as `relation`. Which end receives is being confirmed. |
| Memory link, see "Memory layer" | not yet built | owned by each root |
| Correction | not yet built | a new revision of the corrected join on its own owner, same join id |
| Retained import source, the layer XML or map XML | the import's document address | receiver-owned by that document element |

## Knowledge layer mapping, the MGM best practices layer

Decisions from mgm-main-f8 on 2026-09-23 for the mismatches M1 to M8:
- **M1.** the owner names the layer address. Until then, the address exists only as a placeholder in test fixtures, never in the real import.
- **M2.** Option A. Knowledge accepts any address, root object or not. At an address that is not a root object, it stores a knowledge-only record and creates no functional object. `element` and `recall` at an internal subtype address read the subtype from its parent join, plus the layer items.
- **M3.** Each `(address, provider)` pair resolves at import to its exact join reference. A pair that resolves to no join, or to more than one, fails the import with an error naming the pair.
- **M4.** One item join per practice, keeping the practice id.
- **M5.** Findings and questions are items with a `kind` field.
- **M6.** `knowledge.layer` carries the layer's own metadata in one `metadata` field, and the retained XML is kept too. `code_revision` and `written` are what make a staleness check possible.
- **M7.** The file will carry the full 64-character sha256. The import compares the full value, and a mismatch marks the layer stale. It is not an error.
- **M8.** Accepted: practice fields are open fields on the item join.

Tests added:
- Attaching at `code.bus.event` does not make it a root object, and K7 still holds.
- `element("code.bus.event")` returns the subtype with its layer items.

## Memory layer

Settled on 2026-09-23, as mgm-main-f8 passed it on. Build order: after the chassis and the knowledge layer read side.

The memory layer is a store that agents keep current as they work, by creating, reading, updating and deleting. It has the same shape as the MCP reference memory server, `@modelcontextprotocol/server-memory`.

- **Entities.** Every element and every join in the map is an entity, and each one is a root. Internal subtypes count too: `code.bus.event` is a memory root even though it stays inside its parent's join in the functional graph. An element root is named by its address. A join root is named by its owner address plus its provider.
- **The memory layer is a layer.** Every root links to it through a join the root owns, with the memory layer as provider. That link is a `knowledge.attachment` on the root, whose `source` is the memory layer's `knowledge.layer` join. A join root's link is on its owning element, with `subject` naming the join. An internal subtype's link is a knowledge-only record at its address, as M2 option A.
- **Observations.** The memories on a root. Each is a `memory` join owned by the root, carrying `link`, the reference of that root's link. Agents add, update and delete them. Update writes a new revision of the same join. Delete writes the existing `deleted` flag. History stays, and provenance shows who changed what.
- **Relations.** A relation connects two roots with an active-voice verb. It is a `memory.relation` join owned by the receiving root, with the other root as `provider` and the verb as `relation`. It names roots, not memory revisions. It is not a causal input, so hiding one root does not hide the other.
- **The core map in the same tools.** Following rule 1, the purpose joins of the functional map appear in `read_graph` and `open_nodes` as relations of kind `purpose`, from the receiving element to its provider. Their fields stay the core fields, and memory never mixes into them. Memory relations appear with kind `memory`.
- **Authority.** Adding, updating and deleting observations and relations needs no nonce. A correction to the core needs an orchestrator nonce. The producer is always recorded.

### Automatic links

The MCP server creates the links, and agents never do. More exactly, the knowledge module creates them, as its own operation, so the same happens from the CLI.
- **Where it runs.** The knowledge operation `link_memory(layer)` links every root in the project that has no link to that layer yet. It runs:
  - when a memory layer is configured for a project, as part of that operation;
  - when roots are added. An import through `workflows.import_metaform`, an intake answer sealed on a run, and a correction that adds an element each publish the chassis event `namespace.roots.added` with the added root references. The knowledge module subscribes, and runs `link_memory` for each memory layer as the subscriber's job.
  - The event does not exist today. The workflows importer and the correction operation must publish it.
- **Idempotent.** The link's join id is derived from the layer address, the root address and, for a join root, the subject join id. A second run finds the join and writes nothing. If an identical body is written anyway, the namespace service deduplicates it without a new revision.
- **Provenance.** Each link's producer is the knowledge module's `link_memory` operation. When the event started it, the producer's parent is the importing operation, so the trace shows which import caused the link. No agent nonce is involved.

Open, with f8 confirming:
1. May an agent create a root the map does not have? The choices are yes, recorded as a knowledge-only root, or no, only the map's elements and joins.
2. Are relation verbs free text? The choices are free active-voice text, or a fixed list.
3. Which end of a relation is the receiver?

Tools, against the reference server:

| Reference server | Metaform, MCP name and `metaform <nonce> <name>` | Does |
|---|---|---|
| `create_entities` | `knowledge_create_entities` | Under open question 1, adds roots the map lacks. Map roots already exist and are linked automatically. |
| `create_relations` | `knowledge_create_relations` | Adds `memory.relation` joins on the receiving roots. |
| `add_observations` | `knowledge_add_observations` | Adds memory joins under a root's link. |
| `delete_entities` | `knowledge_delete_entities` | Marks every observation and relation on the root deleted. A map root is never removed from the functional graph. |
| `delete_observations` | `knowledge_delete_observations` | Marks the named observations deleted. |
| `delete_relations` | `knowledge_delete_relations` | Marks the named relations deleted. |
| `read_graph` | `knowledge_read_graph` | Every root with its observations, every purpose join as a `purpose` relation, and every current memory relation. |
| `search_nodes` | `knowledge_search_nodes` | Roots whose address, reading, core fields or observations contain the query. The match is lexical, never by similarity, and the matched text is shown. |
| `open_nodes` | `knowledge_open_nodes` | The named roots with their core fields, observations and relations. |
| none | `knowledge_update_observation` | Replaces an observation's text as a new revision. The store is defined as create, read, update and delete, and the reference server has no update. |
| none | `knowledge_correct` | Writes a correction to a core record as its new revision. It needs an orchestrator nonce, with the corrected record's owner in scope. |

Acceptance tests, written first, on the MGM map in project `mgm`:
1. After import, every root, internal subtypes and join roots included, has exactly one link to the memory layer.
2. A correction that adds an element gives that element its link.
3. Running `link_memory` a second time adds nothing.
4. The link's producer is the knowledge module's `link_memory` operation, and its parent is the import.
5. Agent A adds an observation to `code.failsafe.gateway.mesh` without a nonce. Agent B's `open_nodes` on that address returns it, with A's producer.
6. An observation at `code.bus.event` is stored, and `code.bus.event` is still not a root namespace object.
7. The join root `code.manager.gateway.mesh` with provider `code.failsafe.gateway.mesh` takes an observation, and `open_nodes` returns it on that join.
8. `create_relations` links two roots. The relation is a join owned by the receiving root, with the other as provider. `read_graph` and `open_nodes` show it.
9. `read_graph` shows the map's purpose joins as `purpose` relations, with their core fields unchanged.
10. `update_observation` writes a new revision, and the earlier revision still resolves exactly.
11. `delete_observations` and `delete_relations` hide the items from `read_graph` and `search_nodes`. The retained revisions still resolve, and provenance names who deleted them.
12. `search_nodes("SafeNet")` finds roots by core text and by observation text, and shows the matched text.
13. `knowledge_correct` without a nonce is refused. With one, it writes a new revision, and the prior revision still resolves.
14. Hiding one root does not hide a root related to it.
15. After the owner answers open question 1, a test for a root the map does not have.

---

# Superseded: chassis server with modules plugged in, earlier on 2026-09-23


Status: proposal, 2026-09-23, written by metaform-68 for mgm-main-f8. It is not decided. Everything under "Superseded" below is the earlier two-server design, kept for the record.

Decided: Metaform is an approach to working with AI, not a single trick, so the chassis and module separation is the right one. The base MCP server, once installed, gives the orchestrating agent instructions on how to use it, and each module tells the orchestrator its purpose, so modules must be able to add text to the instructions.

## What exists today

- `modules/mcp/server.py` serves one stdio connection per process. Nothing today is written for an orchestrator. Two launches exist, and both serve assigned work: the harness launches it with `--nonce` for one worker, and a person can configure `metaform mcp` into an agent, which then passes a nonce on every call. Its one instructions string tells an assigned worker how to read and submit its assignment.
- From `Plugin`, only `operations` reach the server today, with their docstrings, their signatures and `operation_visibility` through `runtime.available`. The `operations` and `call` tools use them. `description` and `help` do not reach it.
- `PLUGIN_API_VERSION` is 1, and the loader requires exact equality.
- Uncommitted in `modules/mcp`: `--project` and five workflow tools written into `server.py`, and `--project` on the `mcp` command. That work stopped when this proposal was requested. Its code moves into the workflows module if this proposal is accepted.

## Plugin contract

Two optional fields are added, both with empty defaults:

| Field | Type | Meaning |
|---|---|---|
| `mcp_instructions` | `str`, default `''` | The module's purpose, written for the orchestrating agent: what the module is for and when to use its tools. |
| `mcp_tools` | `tuple[McpTool, ...]`, default `()` | The module's MCP tools. |

`McpTool` is a frozen dataclass in `plugin_contract.py`:

| Field | Type | Meaning |
|---|---|---|
| `name` | `str` | The tool's name inside the module, such as `import`. |
| `operation` | `str` | The module operation it runs. It must be a key of the module's `operations`. |
| `change` | `bool \| Callable[[dict], bool]`, default `True` | Whether a call changes the project and needs an orchestrator nonce. A callable decides per call from the call's arguments. `knowledge_remember` uses one: kind `memory` needs no nonce, and a rule, finding or imperative does. |
| `addresses` | `Callable[[dict], Iterable[str]] \| None`, default `None` | Given the call's arguments, the namespace addresses the call writes. The scope check uses it. |
| `description` | `str`, default `''` | Tool text. Empty means the operation's docstring. |

The input schema comes from the operation's signature, as `operations` builds it today. A tool is a module operation reached through `runtime.invoke`, which is the same path the command line uses. So a tool needs no second implementation, and a tool that composes several steps is a module operation that does so.

`api_version` stays 1. Both fields are additive and have defaults, so every existing module loads unchanged. A module that sets them fails loudly on an older chassis, because `Plugin` rejects the unknown keyword when the module is constructed. If 1 is kept, that failure message is the only notice. A bump to 2 would force every module to change, because the loader requires equality.

## How the chassis collects text and tools

- The base server builds its instructions from the base text below, then one section per contributing module in module id order, headed with the module id. Module id order keeps the text the same from one connection to the next.
- The chassis exposes each module tool as `<module>_<name>`, such as `workflows_import`. The underscore is the reserved separator.
- A dot is not used. The MCP rule, SEP-986 as the installed Python SDK implements it in `mcp/shared/tool_name_validation.py`, allows `^[A-Za-z0-9._-]{1,128}$`, dots included. But Claude reaches an MCP tool as `mcp__<server>__<tool>`, and this session shows Claude Code rewriting a dot and spaces to underscores: the server "claude.ai Claude Docs" appears as `mcp__claude_ai_Claude_Docs__batch`. A dotted name is therefore not reliable from Claude. I recall the Messages API pattern for tool names as `^[a-zA-Z0-9_-]{1,64}$`, and I did not verify it. The names below fit that pattern.
- Base tool names never contain an underscore. Today's base names are `assignment`, `submit`, `status`, `complete`, `abort`, `operations`, `call`, `namespace`, `resolve`, and `trace` is added. Every module tool contains one, so no module tool can shadow a base tool.
- Module ids and tool names may contain underscores themselves, as `harness_runner` and `run_status` do. So two exposed names can still meet, for example module `harness` with tool `runner_run` and module `harness_runner` with tool `run`. The chassis checks every exposed name when it collects tools. If two are equal, it refuses the module whose id sorts later and names both modules and the tool. A repeated `name` within one module is refused at load in the same way.
- A tool name must not contain two underscores in a row, because Claude Code uses `__` to separate server and tool. Exposed names are kept to 64 characters.
- The chassis reads the contributions when it answers `initialize` and `tools/list`. A module that is unloaded or disabled stops contributing on the next list. The chassis refreshes the plugin set before each list, as `operations` does today.
- Open question (b), when a module contributes:
  - **b1**: every loaded and enabled module contributes. Enablement is chassis-wide today.
  - **b2**: only modules enabled for the connection's project contribute. Per-project enablement does not exist today. b2 needs a new per-project setting.

## Base orchestrator text, full draft

> Metaform keeps a project's recorded account of what each part is for: namespace elements joined by the purpose each receiver holds. Modules plug into this server, and each one explains its purpose and tools below.
>
> Reading needs no nonce. Read anything in the project: `namespace` for an element and the joins it owns, `resolve` for an exact revision of a join, and `trace` for the operation, prompt and inputs that produced a record.
>
> Changing the project needs a nonce that the orchestrator issued with `metaform modules activate <module> --project <project> --scope <address>`. The nonce is for one module and one project, and it may change only the addresses under its scope. A tool that changes the project refuses a call without such a nonce, and every change it makes records the nonce. Revoke a nonce with `metaform <nonce> abort`. Workers never issue nonces.
>
> One exception: a memory attached at an element address or a join needs no nonce. Anyone can read and add those memories. They are for sharing knowledge between agents.
>
> To hand work to a worker, start it through a module tool. The worker receives a nonce for its assignment, reads it with `assignment`, and returns its answer with `submit` using the header it was given.

## Where each existing tool goes

| Tool | Now | Goes to |
|---|---|---|
| `assignment`, `submit`, `status`, `complete`, `abort` | base | base, unchanged, for assigned workers |
| `operations`, `call` | base | base, unchanged |
| `namespace`, `resolve` | base, nonce required | base. The nonce requirement changes with option (a). |
| `workflow_import`, `workflow_run`, `run_status`, `result_import`, `latent_run` | uncommitted in `server.py` | `workflows_import`, `workflows_run`, `workflows_run_status`, `workflows_result_import`, `workflows_latent`, contributed by the workflows module over the operations `import_prompt`, a new `run` that composes target and start, `run_status`, `import_metaform` and `latent` |
| `where`, `orient`, `element`, `faces`, `recall`, `remember`, `layer_select`, `layer_mask`, `layer_hide`, `handoff` | planned | contributed by the knowledge module as `knowledge_<name>` |
| `trace` | planned | base, because provenance belongs to the chassis in `src/metaform/production_joins.py` |

## Authority for contributed tools

The chassis evaluates `change` for each call, calling it with the call's arguments when it is a callable. When the result is True, the chassis applies one check before it invokes the operation:
1. A nonce is supplied, it exists, and it is neither completed nor aborted.
2. Its project is the connection's project, and its module is the tool's module.
3. If the nonce has a scope, every address that the tool's `addresses` returns for this call lies at or under a scope address. A change tool without `addresses` cannot be scoped. It accepts only a nonce without a scope, and it refuses a scoped nonce rather than letting it through unchecked.
4. The operation runs with that nonce in its context, so the producing record names it.

A call whose `change` evaluates to False runs with no nonce, under the connection's project. `knowledge_remember` with kind `memory` is the only planned write of this kind. It still records its producer. If the callable raises, the call is refused and the error is returned.

The connection's project is set by `metaform mcp --project <project>`.

- Open question (a), what a worker launched with `--nonce` sees:
  - **a1**: the base worker instructions, only its assigned module's section, and only that module's tools.
  - **a2**: the same instructions and tools the orchestrator sees. Its nonce still authorizes only its own module and scope.

## Acceptance tests, written first

New chassis tests with a fixture module:
1. The server's instructions contain the base text, then the fixture module's `mcp_instructions` under its id. A second fixture module's section follows in module id order.
2. The fixture tool is listed as `<module>_<name>` and runs its operation through `runtime.invoke`. After the module is disabled, the next list has neither its section nor its tool.
3. Two fixture modules that both contribute a tool named `run` are listed as two distinct tools. A module that repeats a name within itself fails to load, and the error names both. Fixture modules `alpha` with tool `beta_run` and `alpha_beta` with tool `run` both expose `alpha_beta_run`: the later id is refused, and the error names both modules. Every listed name matches `^[a-zA-Z0-9_-]{1,64}$` and has no `__`.
4. A change tool refuses a call with no nonce, an unknown nonce, a revoked nonce, another project's nonce and another module's nonce. It refuses an address outside scope, and a scoped nonce when it has no `addresses`. With a valid nonce, the producing record names it.
5. A tool with `change=False` runs without a nonce.
6. A tool whose `change` is a callable that returns True for `kind="rule"` and False for `kind="memory"`: the memory call runs without a nonce, the rule call without a nonce is refused, and the rule call with a valid nonce runs and records it.
7. A module that sets neither new field loads and behaves as before, with `api_version` still 1.

The workflow tests in `tests/test_workflow_mcp.py` keep every assertion. Only the tool names change to `workflows_*`. Test 6 of that file moves into chassis test 4.

The knowledge tests keep their assertions under `knowledge_*` names. Knowledge test 8 rests on chassis test 6. Test 7, agent A remembers and agent B recalls, uses the `change=False` path.

Options (a) and (b) each add one test once the owner chooses.

---

# Superseded: earlier two-server design

## Metaform agent MCPs: workflow and knowledge

Status: draft, 2026-09-23. The owner: two servers, one for importing workflows and one for knowledge layers. Two servers with separate jobs. Both go only through the platform's public operations, and neither owns a store.

---

## Authority

2026-09-23: agents need a nonce from the orchestrator to change their project; without one the MCP server allows changing nothing but agent memories.

His correction the same day: the memories allowed without a nonce are memories tied to places in the metaform, at an element address or a join. Anyone can read them and add them, because they are for sharing knowledge. There is no private per-agent memory.

- Without a nonce, an agent can read everything and attach a memory at any address or join. The producer is recorded for provenance. Nothing restricts who reads or adds.
- Every other write needs a change nonce issued by the orchestrator: rules, findings, imperatives, layer attach, select, mask and hide, namespace joins, and every workflow write.
- The orchestrator issues a change nonce with `metaform modules activate <module> --project <project> [--scope <address> ...]`. This is the existing activation nonce with an address scope added. No `--scope` means the whole project. It revokes the nonce with `metaform <nonce> abort`. Workers never mint nonces, and the MCP server has no tool that issues them.
- The MCP server checks every write: the nonce exists, it is neither completed nor aborted, its project is the server's project, its module owns the operation, and each address the call names sits at or under one of the nonce's scope addresses. A write that fails the check is refused.
- A write made under a nonce runs with that nonce in its operation context, so the producing record names the nonce. `trace` shows who authorized a change as well as who made it.
- The scope check covers the addresses a call names. When a run's intake answer is sealed, the import writes wherever the answer places its elements. That write is the authorized run's own result.

---

## 1. Workflow MCP: import procedures and run them

Its job: get an authored procedure such as the Canonical Intake into Metaform unchanged, run it on a target, and land the answer in the record as receiver-owned joins with provenance.

The model is the Canonical Intake itself: a `process` with `target`, `core_concepts`, `namespace_rules`, method `steps`, a `persistent_directive`, an `output_instruction` and a `response_protocol` schema. A result `id` lets `digital-typology-expand.xml` link back to it.

The tools are a second tool set in the existing `mcp` module, served with `--project <project>`. The existing nonce tools stay as they are.

| Tool | Nonce | Operations used | Does |
|---|---|---|---|
| `workflow_import` | change | `workflows.retain_source`, `workflows.create` | Retains the authored text exactly and creates a one-step definition. The step's first segment is that text as a literal, followed by the bound target. The definition records the source reference and its sha256. Nothing runs. A re-import of changed text is a new revision, and earlier runs keep theirs. |
| `workflow_run` | change | `workflows.target`, `workflows.start` | Records the target: its path, its revision, which is a commit or the working tree with `git status --short` recorded, and its exclusions. Starts the definition revision with the target bound, and with the worker settings recorded in the run state. Returns the run, its drive job and the first assignment's nonce. |
| `assignment` / `submit` / `complete` / `abort` / `status` | assignment | existing | The worker gets the exact issued prompt and submits its answer with the required header. |
| `run_status` | none | `workflows.run_status` | A run's outputs, pending assignments, accepted answer and the materialized import with its diagnostics. |
| `result_import` | change | `workflows.import_metaform` | Imports a result produced outside a run. |
| `latent_run` | change | `workflows.latent` | Runs the latent pass on a retained native account, with worker settings. |

How the platform behaves, checked in `modules/workflows` on 2026-09-23:
1. `workflows.import_workflow` does run something. It retains the source, then `prepare` starts an agent run that converts it to the execution grammar. Only `retain_source` imports without running. The Canonical Intake needs no conversion, because it is issued as one authored prompt.
2. For a run, result import is not a separate step. When a step whose `result_handler` is `intake` has its answer sealed, `execution._materialize` imports it into the record. `result_import` is for results produced outside a run.
3. There is no schema validator, and none is added. The importer keeps every answer as `intake.source`, materializes whatever parses, and records diagnostics. Nothing is rejected, and nothing is handed back to the worker.
4. The latent worker receives the retained Native account in a fresh work folder. The account is the answer XML with its path refs. Nothing stops a harness from reading the filesystem, and no gate is added.
5. A binding segment prints the object's name before the joined text. So the authored text goes in as a literal segment, which keeps it byte-identical.
6. The importer keeps `provider`, `vested` and the `VE` and `AUE` roles as attributes. An `<element graph="internal">` nested in a `<join>` stays inside that join's value and is not made a root namespace object.
7. `workflows.intake`, which runs the hardcoded runtime copy of the intake, stays unchanged until the owner decides.

Worker settings: the run carries `worker` with `provider`, `model` and `effort`. The Claude preset passes `--model` and `--effort`. The Codex preset passes `-m` and `-c model_reasoning_effort=`. The harness evidence records the exact command.

Project per artifact: a run executes in the server's project. If that project has no folder, it is registered at the target's folder. A registered folder is never repointed.

Acceptance tests, written first and shown failing:
1. `workflow_import` of `specifications/Canonical_Intake.xml`: the retained text and the definition's first segment equal the file's bytes, the sha256 is recorded, and no run starts.
2. `workflow_run` on a fixture artifact in project `mgm`: the issued prompt holds the whole process text and the target's path, revision and exclusions. The run state records the worker. Project `mgm` is registered at the fixture folder, and another project's folder is unchanged.
3. The Claude preset with `{model: sonnet, effort: high}`: the recorded harness command contains `--model sonnet --effort high`.
4. A new-schema answer sealed on an `intake` step: root elements are objects, joins are owned by the RE and keep `provider`, `role="VE"` and `vested` are kept, and the nested `graph="internal"` subtype is not a root object but is present in its parent join's value.
5. `latent_run`: the prompt contains the Native account, not a token that appears only in the artifact's file, and its working folder is not the artifact folder.
6. Authority: without a nonce, `workflow_import` and `workflow_run` are refused. With an orchestrator nonce scoped to the project they succeed, and the producing record names the nonce. A nonce scoped to one address cannot write another. After `abort`, the nonce is refused. `run_status` needs no nonce.
7. A malformed answer is kept as `intake.source` with a diagnostic, and the run completes.

---

## 2. Knowledge MCP: layers for agents at work

Its job: an agent working in a project, with no assignment, can find where it is, read the function and the rules there, record what it learned, and hand scoped context to a sub-agent.

2026-09-23: knowledge layers are where non-functional things live: medium, encoding, language, style and genre. Any namespace address can be linked into a knowledge layer. The Canonical Intake's validity rules do not apply to layer names or to the addresses layers link. A `code.c` layer carrying C concerns is legal, even though `code.c` is invalid in the functional map.

| Tool | Does |
|---|---|
| `where` | Maps a file path or symbol to the elements and joins whose refs cite it. |
| `orient` | Maps free text to candidate addresses whose reversed names match its nouns. It is lexical and shows the matched tokens. It is never a similarity fetch. |
| `element` | Returns an address's core (role, joins it owns as RE, joins where it is provider, internal subtypes) plus the layers projected there under the selection and mask rules. Core and layers are never mixed in one field. |
| `faces` | Returns the (receiving entity, operative purpose, encounter function) triangles involving the address: the faces a change there must keep intact. |
| `recall` | Returns memory, rules, findings and imperatives attached at an address or join and inherited from the trunk, each with provenance. |
| `remember` | Attaches a memory, rule, finding or imperative at an address or join, as a revision with producer provenance. It never rewrites. |
| `layer_select` / `layer_mask` / `layer_hide` | The knowledge module's selection, mask and visibility, per `modules/knowledge/README.md`. |
| `trace` | Returns a record's producing operation, exact prompt and input revisions, recursively. |
| `handoff` | Renders a block for a sub-agent: the task, then the selected layer items at the given addresses under their layer names, then an address footer. Masked layers never appear. |

Reads and `remember` of a memory need no nonce. Every other write needs an orchestrator change nonce, as the Authority section states. Every write records its producer.

Acceptance tests (write first; they must fail first), on the MGM map imported as project `mgm`:
1. `where("src/mgm_safetynet.c")` returns `code.failsafe.gateway.mesh` and its internal subtypes.
2. `orient("SafeNet false trips")` includes `code.failsafe.gateway.mesh` and `code.window.probe`, with the matched tokens.
3. `element` on the DE returns joins in both directions and at least one internal subtype.
4. `remember` then `recall` round-trips with provenance. A child address inherits it when selection allows, and a mask blocks it.
5. `handoff` contains the task, the selected layer items and an address footer, and no masked layer.
6. No read tool needs a nonce.
7. Agent A remembers at `code.X` without a nonce, and agent B recalls it at `code.X`.
8. Without a nonce, `remember` of a rule, finding or imperative, and every layer write, is refused.
9. A layer named after an address the intake rules call invalid, such as `code.c`, attaches and projects normally.

---

## Order

Build the workflow MCP first, so the MGM intake runs through it with a Sonnet worker at high effort. Build the knowledge MCP second, on that result.
