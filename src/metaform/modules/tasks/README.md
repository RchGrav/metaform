# Assigned tasks and project skills

Tasks define assigned work. Skills supply instructions selected as the agent's functional context changes.
The four named tasks are:

| Task | Purpose | Canonical instruction file |
| --- | --- | --- |
| `user_agent` | Interact with the user and perform or delegate requested work. | `resources/user_agent.txt` |
| `worker` | Remain available for paired project work and discover node expertise. | `resources/worker.txt` |
| `ticket_creation` | Write a ticket for two agents, with a summary and intended allocation. | `resources/ticket_creation.txt` |
| `facilitator` | Author reusable skills or skills attached to a receiving element. | `resources/facilitator.txt` |

The user-authored User Agent, Worker and Facilitator prompts are preserved in their resource files. Delivery binds
`{project}` and the worker's `{name variable}`. The later instruction to end a finished run is kept separately in
`resources/worker_lifetime.txt` and appended for workers, preserving the original Worker prompt.

Use `metaform tasks` with these operations:

- `list node=...` discovers named tasks and expertise metadata for that functional arrival.
- `read name=worker` reads the selected task's complete instructions. The canonical resource is
  `metaform://tasks/definitions/worker`.
- `assign name=worker text="..." node=... skills='["skill-id"]'` starts a dedicated worker with selected skills.
  `assign text="..."` also accepts an explicit assignment without a named definition.
- `get id=...`, `update id=... responses=...`, and `cancel id=...` follow durable execution and answer its input requests.
- `configure id=...` lists native adapter settings. Supply `setting=... value=...` to use an advertised option.

`folder` selects the working directory and a registered target project's context. Default dispatch opens `user_agent`.
Task instructions and selected skill documents are read individually rather than loading every task or project skill.
Assignments can select expertise item IDs or canonical reusable skill URIs. Supporting file bodies remain available through individual resource reads.

## Skill placement and reads

Reusable skills are authored with `tasks reusable name=... text=...`, adding `description=...` for a plain instruction
body and optional `files=...` for supporting text resources. Their source is `<Metaform home>/skills/<name>/`.
The MCP server exposes these through `io.modelcontextprotocol/skills`: `skills/list`, `skills/get`, and ordinary
`resources/read`. A reusable skill's canonical URI is `skill://<name>/SKILL.md`. Packaged native skills use the
separate `skill://metaform/<name>/SKILL.md` namespace.

Project agent skills are knowledge items in the `expertise` layer. An element's item stores skill documents inline
under its `joins` key. Skills attached to actual functional joins are stored on those joins. Both use the same
SKILL.md, YAML frontmatter and resource-manifest representation as reusable skills. Supporting references can name
reusable skills by canonical URI.

`tasks expertise op=write node=... name=... text=...` stores a skill at an existing element or `join:<id>`.
`op=list node=...` returns metadata at the arrival and its functional joins. `op=read skill=... node=...` reads one
selected document by scoped name, item ID or URI. Known graph skill URIs are directly readable through the MCP
resource provider without enumerating the project's expertise.

Authored SKILL.md bytes and all frontmatter fields are retained. Static manifests list every file exactly once,
including SKILL.md, with its SHA-256 digest and raw byte count. The shared representation checks relative paths,
matching skill names and URIs, and the 512-file/16 MiB limits.

## Worker board and paired work

The board is kept in `<temporary directory>/.metadata/<project-id>/sessions.sqlite`, using `TMPDIR` when set.
Server restarts and page refreshes reopen these records. The browser reads the server's board through the existing
page event path. Native sessions retain their context while idle and receive queued messages or partner-completion
wakes through native events.

The panel shows:

```text
agent-name  rating %  context %  complete %
Next
{task_phrase} ({name})
Current
{task_phrase} ({name}, ...)
Past
{task_phrase} ({name}) rating %
```

Node names are preserved verbatim. The headline rating averages completed-round scores. Context percentage uses
the adapter's reported usage and capacity. Completion is checked/total worksheet items for that agent, including
shared items. Unreported values remain unknown. Agent-facing board reads omit the calling worker and its ratings.

`ticket` records a summary phrase and requested work. `worksheet` registers stable checklist items and planned
element allocation. `pair` records the partnership accepted through messages. `status` updates current/next work,
node names and availability. `message` queues attributed messages. Partner selection, invitations and turn-taking
follow the Worker task's prompted behavior.

`check` marks an item and recalculates progress. At N/N the completed worksheet is appended to the ticket. Both
partners submit `rate` with their chosen category scores, totalling at most 100 points. The ticket closes when all
items and both counterpart ratings are recorded. Waiting peers are then woken, and workers can choose further
tickets. Once all work is complete and workers are idle, their contexts end and the completed run's board records
are cleared. Tickets and their completed worksheets remain in the project store.

## MCP task lifecycle

Assigned execution follows the [MCP Tasks extension](https://modelcontextprotocol.io/extensions/tasks/overview),
stable base schema 2026-07-28. The assignment is stored before ACP launch and before returning a flat
CreateTaskResult. Clients negotiate `io.modelcontextprotocol/tasks` for asynchronous launch and use `tasks/get`,
`tasks/update`, and `tasks/cancel`. Native events update durable status. Client polling requires no server polling loop.
Input responses are durably queued, duplicate responses are ignored, cancellation is cooperative, and terminal
records remain immutable. Native/tool failures complete with `isError`; JSON-RPC execution failures use `failed`.

The Skills transport follows the [MCP Skills extension](https://modelcontextprotocol.io/extensions/skills/overview)
and its [stable specification](https://github.com/modelcontextprotocol/ext-skills/blob/main/specification/stable/skills.mdx).

Automatic ticket queues, Full Auto controls, managed retry/wave/hold-review execution and creator-only stopping are retired.
A2A and Paperclip expose tickets for agent selection. Issue reports use an explicit User Agent assignment. Native target,
state, resource and option checks remain shared by all agents.
