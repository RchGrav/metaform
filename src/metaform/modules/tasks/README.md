# Assigned tasks and project skills

## Purpose

Tasks define assigned work. Skills supply instructions selected as the agent's functional context changes.
The named tasks are:

| Task | Purpose | Canonical instruction file |
| --- | --- | --- |
| `user_agent` | Interact with the user and perform or delegate requested work. | `resources/user_agent.txt` |
| `project_agent` | Persistent paired work in a shared worktree spanning tickets, with the skill layer at the node. | `resources/project_agent.txt` |
| `composer` | Write the tickets for pairs of agents and put each in its worktree. | `resources/composer.txt` |
| `facilitator` | Author reusable skills or skills attached to a receiving element. | `resources/facilitator.txt` |
| `architect` | Expand refined plans into technical specifications grounded in the project. | `resources/architect.txt` |
| `intake` | Analyze a project and record its functional map. | `../intake/resources/intake.xml` |

## Template version

The introducing change did not record a template version. The module uses the current `Module`, `Verb` and table declarations.

## Declaration

`SUPPORTED_OS` names Linux, macOS and Windows. `DEPENDENCIES` is empty. `SHIPS_DISABLED` is false and `REMOTE_AGENT` is true.
`MODULE` declares task and skill verbs, the task-definition resource, one subscription and two providers.
`task.lifecycle` exposes assigned execution. `skill.document` resolves project skill resources.

## Common base used

`metaform.module` supplies contexts, verbs, resources and runtime providers. `metaform.data` supplies project records and skill layers.
`metaform.settings` declares pair choices and automatic worktree merging. `metaform.prompt_files` resolves selected task instructions.
`metaform.skills` stores reusable skills. `metaform.home` locates registered projects and durable task records.

## Prompts

The user-authored User Agent, Project Agent, Facilitator and Architect prompts are preserved in their resource files.
Delivery binds `{project}` and the agent's `{name variable}`. The project agent never ends on its own: when work runs
out it goes to Standby, as its instructions say.

The `intake` task uses the existing intake instruction file as its one source. Task reads, assignments and
`intake prompt` resolve the same selected editable prompt text. Intake instructions are opaque UTF-8 text:
their file extension, headings, tags and strings such as `{prompt}` do not define a runtime contract or a
substitution slot. `--intake-file=<path>` selects a custom instruction file. No XML form or prescribed method
sections are required, and changes to the authored method remain intact.

Use `metaform tasks read name=intake` to read it and `metaform tasks assign name=intake text="Map this project."`
to assign it. Assignment keeps the selected instruction body and supplied input separately. The
`intake prompt text="..."` reader appends a literal request under `## Intake request` without rewriting the body.

## Verbs

Each CLI verb is also an MCP tool named `tasks_<verb>`.

Use `metaform tasks` with these operations:

- `list node=...` discovers named tasks and the skill layer's metadata at that functional arrival, followed by the reusable
  skills of the Metaform home, each with its name, description and `skill://<name>/SKILL.md` URI.
- `read name=project_agent` reads the selected task's complete instructions. The canonical resource is
  `metaform://tasks/definitions/project_agent`.
- `start` starts a pair of project agents, even for one ticket. The settings `tasks_agent_1` and `tasks_agent_2`
  choose each agent of the pair, so one can be Claude and the other Codex; each agent's model and thinking level
  are the person's own `dispatch_<agent>_model` and `dispatch_<agent>_effort` settings. Nothing chooses for the person.
- `assign name=project_agent text="..." node=... skills='["skill-id"]'` starts one dedicated agent with selected
  skills. `assign text="..."` also accepts an explicit assignment without a named definition.
- `get id=...`, `update id=... responses=...`, and `cancel id=...` follow durable execution and answer its input requests.
- `configure id=...` lists native adapter settings. Supply `setting=... value=...` to use an advertised option.

`folder` selects the working directory and a registered target project's context. Default dispatch opens `user_agent`.
Task instructions and selected skill documents are read individually rather than loading every task or project skill.
Assignments can select skill layer item IDs or canonical reusable skill URIs. Supporting file bodies remain available through individual resource reads.

## Skill placement and reads

Reusable skills are authored with `tasks reusable name=... text=...`, adding `description=...` for a plain instruction
body and optional `files=...` for supporting text resources. Their source is `<Metaform home>/skills/<name>/`.
The MCP server exposes these through `io.modelcontextprotocol/skills`: `skills/list`, `skills/get`, and ordinary
`resources/read`. A reusable skill's canonical URI is `skill://<name>/SKILL.md`. Packaged native skills use the
separate `skill://metaform/<name>/SKILL.md` namespace.

Project agent skills are the skill layer: knowledge items in the layer `skills`, tagged `skill`, each addressed as
`skill://skills/<node>/<name>/SKILL.md`. An element's item stores skill documents inline
under its `joins` key. Skills attached to actual functional joins are stored on those joins. Both use the same
SKILL.md, YAML frontmatter and resource-manifest representation as reusable skills. Supporting references can name
reusable skills by canonical URI.

`tasks skills op=write node=... name=... text=...` stores a skill at an existing element or `join:<id>`.
`op=list node=...` returns metadata at the arrival and its functional joins. `op=read skill=... node=...` reads one
selected document by scoped name, item ID or URI. Known graph skill URIs are directly readable through the MCP
resource provider without enumerating the project's skill layer.

Authored SKILL.md bytes and all frontmatter fields are retained. Static manifests list every file exactly once,
including SKILL.md, with its SHA-256 digest and raw byte count. The shared representation checks relative paths,
matching skill names and URIs, and the 512-file/16 MiB limits.

## Assignments, worktrees, the board and paired work

The composer puts tickets that land together in one worktree with `ticket ... worktree=<name>`; a ticket given none
is an assignment of its own, named by its id. A ticket may also name the agents who work it, `agents=[...]`: the
first named claims it, the next is its partner, and each one online is told. The tasks module keeps both in its
`tickets` table.

The board is kept in `<temporary directory>/.metadata/<project-id>/board.sqlite`, using `TMPDIR` when set.
Server restarts and page refreshes reopen these records. The browser reads the server's board through the existing
page event path.

`board` answers with the other agents online and the assignments open on the project. Each agent shows its score,
context percentage, completion percentage, and its next, current and past assignments; the caller's own row and
score are omitted. Each assignment shows its tickets (each with `taken` and `held`), the agents named on them and,
once claimed, its holder, partner and progress, so an agent can pick the next free one.

`worksheet worktree=<name> items=[...]` is the claim: it takes every open ticket in the assignment and registers the
unified checklist. An item may name its `ticket`, `agent` and `nodes`; an item naming no ticket is shared by all.
The items are the plan the board shows, and each participant's planned nodes, from the items' `nodes`, show on the
board so a partner can discover the skills it needs. When the composer put the tickets in a worktree, the claim also
makes the git worktree `.worktrees/<name>` on the branch `metaform/<name>` from the checked-out HEAD, kept out of
git status through `.git/info/exclude`; a ticket claimed by its own id is worked in the project folder, and so is a
project folder outside git. An assignment another agent holds is theirs: a second claim is refused with the holder
named, and only the holder registers its worksheet again. `pair` records the partnership accepted through messages.
`status` updates current and next assignment, node names and availability.

`message` queues an attributed message and logs each one, sender, recipient, text and time, in the board database
for the run. An idle agent is woken with its queued messages; a working agent reads
them on its next tasks tool call, where every tasks result carries them as `messages`, so a message never waits for
the end of a long turn and none is delivered twice.

`check` marks an item. Each ticket's steps follow its own items and the shared ones, and at N/N the completed items
are appended to each ticket. Completion is checked/total worksheet items for that agent.

## Ratings and scores

Every agent online starts at a score of 100; 105 is the most it can reach. At N/N each participant calls `rate`:
`target=<id>` with `scores` as stars of five in each category, Efficient (10), Alert & Aware (20), Thorough (30)
and Coordination (40), and `bonus=true` when the rated agent improved the final work beyond critiquing it (+5); or
`alone=true` when there was no one to rate. Each category gives weight × stars ⁄ 5 points, so four stars in
Coordination cost eight points; the bonus adds five, within 0 and 105. A pick made again replaces the first. The
assignment closes once every participant has rated or said alone: its tickets are done, waiting peers are woken, and
the participants are told to take turns when assignments remain: the prior partner picks the next assignment first,
then messages the prior coordinator. The rated agent is never shown the score it was given or its own.

A score belongs to a context, the agent's session. When an agent shuts down its score clears with it, since a fresh
agent starting a new context carries no penalty; when the same session is resumed, its score comes back with it. The
board keeps each session's score in its `scores` table, written whenever a score moves and read back when a worker
row gains that session id; a worker with no session id yet is at 100. Anyone online may rate anyone else.

With the `tasks_full_auto` setting on (Full Auto), the close of an assignment the composer put in a worktree commits
what the worktree holds, merges its branch into the branch checked out in the project folder, and removes the
worktree and branch; a ticket worked in the project folder runs no git at its close. A merge git refuses is undone,
the worktree stays, and git's words are noted on the tickets; closure never waits on the merge. Off, the worktree
and branch stay for the person to merge.

## MCP task lifecycle

Assigned execution follows the [MCP Tasks extension](https://modelcontextprotocol.io/extensions/tasks/overview),
stable base schema 2026-07-28. The assignment is stored before ACP launch and before returning a flat
CreateTaskResult. Clients negotiate `io.modelcontextprotocol/tasks` for asynchronous launch and use `tasks/get`,
`tasks/update`, and `tasks/cancel`. Native events update durable status. Client polling requires no server polling loop.
Input responses are durably queued, duplicate responses are ignored, cancellation is cooperative, and an ended
task's record stays as recorded while its session is ended. Native/tool failures complete with `isError`; JSON-RPC
execution failures use `failed`.

## Calling a closed context back, and handing off

A closed context can always be called back, because finding out what happened needs the context that was there.
`dispatch talk session=<work>:<session>` and `dispatch resume <work> session=<session>` resume an ended project
agent's session in place, as the same agent with its own memory, where its agent offers session/resume or
session/load; the task comes out of its terminal state once the session is observed running, and the agent is back
on the board with its session's score. Where the agent can do neither, a new session of the same agent starts and
reads the ended thread, and the answer says so (`new_context: true`). `message` to an ended agent calls its context
back the same way and is delivered once the session is on the board again.

Project agents stay running and hand off rather than shut down and come back. The task text tells the agent to hand
off at 50% of its context: finish the task in hand, write a handoff and call out its replacement. Nothing times or
reminds it; the harness shows the agent its own context. `handoff text=<handoff>` starts a new project agent on the
same agent with the handoff as its input, moves the caller's place on the board to it, holder or partner in every open
round, its current and next assignment and its queued messages, and ends the caller's own task. The newcomer is a
fresh context at 100.

The Skills transport follows the [MCP Skills extension](https://modelcontextprotocol.io/extensions/skills/overview)
and its [stable specification](https://github.com/modelcontextprotocol/ext-skills/blob/main/specification/stable/skills.mdx).

Automatic ticket queues, managed retry/wave/hold-review execution and creator-only stopping are retired.
A2A and Paperclip expose tickets for agent selection. Issue reports use an explicit User Agent assignment. Native target,
state, resource and option checks remain shared by all agents.

## Settings

`tasks_agent_1` defaults to Claude and `tasks_agent_2` defaults to Codex.
Each slot's `_model` and `_effort` settings default to `default`, using that agent's dispatch settings.
`tasks_full_auto` defaults to false. Its worktree merge behavior is described under Ratings and scores.

## Events

The module subscribes to `map.changed` for native task state and board changes.
Board updates publish `map.changed` with `tasks.board`, affected agent and ticket identities, and the worktree.
The event's `wake` flag identifies changes that require agent delivery.

## Sync and async

All declared command and subscription handlers are synchronous.
Assignments launch through the native transport and return durable task identifiers before that work finishes.

## Layers

Project skills live in the mutable, hideable `skills` layer, owned by `tasks` and tagged `skill`.
Each instruction retains its document bytes, frontmatter, resources and attachment to an element or functional join.

Project tables use version 4, compatible from 1:

- `assignments`, keyed by task ID, stores instructions, execution state, input requests, native locator and terminal result.
- `tickets`, keyed by work ID, stores worktree grouping and assigned agents.

The board's SQLite records are separate from these project tables. Their location and lifetime are described above.

## Lifecycle and cleanup

The module declares no start or stop hooks. Dispatch owns native agent processes and their shutdown.
Task cancellation records the request before passing it to the transport. Terminal task records remain readable.
Worktrees remain until explicitly removed or closed under the Full Auto setting.

## Modules relied on

Dispatch supplies `task.transport`, available agents and native option choices through providers.
Intake supplies the selected instructions for the `intake` task.
Project skill discovery reads existing functional elements and joins through the common data interface.

## Systems supported

Linux, macOS and Windows. Native agent availability depends on the enabled transport and installed adapter.

## Resources owned

The module owns assignment and ticket metadata, project skill records, board records and worktrees created for assignments.
Reusable skill files live under the Metaform home's skills folder. Dispatch owns agent process resources.

## Installed and direct wheel

Both forms carry the same task instruction resources and use the same project records and providers.
Execution requires an enabled native transport. Reading definitions and reusable skills does not launch an agent.

## Demonstration

From a registered project folder:

```bash
metaform tasks list
metaform tasks read name=project_agent
metaform tasks board
```
